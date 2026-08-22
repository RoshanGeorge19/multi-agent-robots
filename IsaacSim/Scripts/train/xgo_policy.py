"""Load a trained XGO locomotion policy for use as a frozen low-level controller.

The maze environment needs to *run* this policy, not train it, so this rebuilds
the network from a skrl checkpoint with plain torch rather than pulling skrl into
the inference path.

Layer indices follow skrl's model instantiator: `net_container.{0,2,4,6}` are the
linear layers with activations in between.
"""

from __future__ import annotations

import torch
import torch.nn as nn


class RunningStandardScaler:
    """Inference half of skrl's observation preprocessor.

    The policy was trained on normalised observations, so feeding it raw ones
    produces nonsense. The statistics are frozen at their trained values.
    """

    def __init__(self, mean: torch.Tensor, variance: torch.Tensor, clip: float = 5.0):
        self.mean = mean
        self.variance = variance
        self.clip = clip

    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        normalised = (x - self.mean) / torch.sqrt(self.variance + 1e-8)
        return normalised.clamp(-self.clip, self.clip)


class XGOLocomotionPolicy:
    """Frozen velocity-tracking policy: observation in, joint offsets out."""

    def __init__(self, checkpoint_path: str, device):
        self.device = device
        state = torch.load(checkpoint_path, map_location=device, weights_only=False)

        policy = state["policy"]
        weights = [policy[f"net_container.{i}.weight"] for i in (0, 2, 4, 6)]
        biases = [policy[f"net_container.{i}.bias"] for i in (0, 2, 4, 6)]

        layers: list[nn.Module] = []
        for idx, (w, b) in enumerate(zip(weights, biases)):
            linear = nn.Linear(w.shape[1], w.shape[0])
            linear.weight.data.copy_(w)
            linear.bias.data.copy_(b)
            layers.append(linear)
            if idx < len(weights) - 1:
                layers.append(nn.ELU())

        self.net = nn.Sequential(*layers).to(device).eval()
        for param in self.net.parameters():
            param.requires_grad_(False)

        self.dtype = weights[0].dtype
        self.obs_dim = weights[0].shape[1]
        self.action_dim = weights[-1].shape[0]

        # Cast the stored statistics too: skrl saves them as float64, and
        # normalising a float32 observation with float64 stats promotes the
        # result back to float64, which then fails the matmul.
        pre = state["observation_preprocessor"]
        self.preprocessor = RunningStandardScaler(
            pre["running_mean"].to(device=device, dtype=self.dtype),
            pre["running_variance"].to(device=device, dtype=self.dtype),
        )

    @torch.no_grad()
    def act(self, observations: torch.Tensor) -> torch.Tensor:
        """Deterministic action: the Gaussian policy's mean, not a sample.

        Observations are cast to the network's dtype: callers assembling them from
        mixed sources can easily end up with float64, which fails the matmul with
        "mat1 and mat2 must have the same dtype".
        """
        observations = observations.to(dtype=self.dtype, device=self.device)
        return self.net(self.preprocessor(observations))

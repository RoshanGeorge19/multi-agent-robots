---
title: "Negotiation and Deadlock Resolution between Autonomous Mobile Robots in Constrained Spaces: A Literature Review"
subtitle: "Positioning the head-on corridor / pull-in-bay study (TurtleBot3 Waffle, ROS 2 Jazzy, Gazebo Harmonic)"
date: "October 2026"
bibliography: references.bib
link-citations: true
---

> **How to read this document.** Citations use Pandoc syntax (`[@key]`); every key resolves to an entry in [`references.bib`](references.bib), and each entry carries a DOI, an arXiv e-print ID, or a stable URL. Every reference was checked on 2026-10-14 against Crossref, OpenAlex, the arXiv API or the cited web page. Papers that could not be verified were left out. A rendered PDF with a full reference list can be produced with `pandoc literature_review.md --citeproc -o literature_review.pdf`. Where a summary relies on the abstract and not the full text, the comparison table says so.

## 1. Executive summary

The planned study puts two (later three or more) AMRs head-on in a corridor that is only one robot wide and has one or more pull-in bays (passing places). One robot has to reverse or detour into a bay so the other can pass. The literature that bears on this problem is large, but it is split across at least nine communities that rarely cite one another:

1. **Deadlock theory for reactive controllers.** Control-barrier-function (CBF) and velocity-obstacle controllers stall in symmetric, constrained configurations [@grover2023before; @zheng2023deadlock; @dergachev2021distributed]. This failure motivates the "no communication" baseline.
2. **Fleet coordination with formal guarantees.** Loosely coupled supervisory controllers and robust plan execution give safety and liveness guarantees under delays and communication faults [@cap2016provably; @pecora2018loosely; @mannucci2019provably; @mannucci2021provably; @honig2019persistent].
3. **AGV zone control and industrial traffic management**, from Petri-net and zone-based deadlock avoidance to hierarchical traffic managers [@fanti2002event; @reveliotis2000conflict; @geozone2023; @hiertraffic2023], and the interfaces that industry standardised: Open-RMF/`rmf_traffic`, VDA 5050, MassRobotics and ISO 3691-4 [@openrmf; @rmftraffic; @vda5050; @massrobotics; @iso36914].
4. **MAPF and prioritised planning**, the natural centralised oracle [@sharon2015cbs; @barer2014suboptimal; @okumura2022pibt; @okumura2023lacam; @li2021lifelong]. This includes recent narrow-corridor work [@experience2024narrow; @nodetorobot2023; @macga2025] and kinodynamic work [@kottinger2022conflict; @wen2022clmapf; @dbecbs2025].
5. **Explicit negotiation, auctions and mechanism design**, from Contract Net to non-cooperative MAPF auctions [@smith1980contract; @gerkey2002sold; @dias2006market; @gautier2022negotiated; @amir2015mapfauction].
6. **Game-theoretic "social mini-games"**: doorways, hallways and intersections treated as non-cooperative games with CBF-based liveness [@chandra2025deadlock; @chandra2026social; @chandra2023decentralized].
7. **Multi-agent RL**, including give-way/corridor scenarios in VMAS [@bettini2022vmas; @bettini2023heterogeneous; @vmasgiveway] and learned hallway passing [@park2023hallucination].
8. **LLM-based negotiation (2023 onward)**: RoCo [@mandi2024roco], foundation-model deadlock resolution [@garg2024llm], GameChat [@gamechat2025] and MARLIN [@marlin2024]. MARLIN uses **two TurtleBot3 Waffle robots in slotted corridors**, which makes it the closest existing physical setup to this study.
9. **Road-traffic analogues**: single-track roads with passing places [@highwaycode; @narrowpassageuk2023], bottleneck negotiation between connected vehicles [@bottleneckiv2023; @avmvbottleneck2023] and auction/game-theoretic intersection management [@dresner2008multiagent; @carlino2013auction].

**Main finding.** No widely adopted benchmark exists for *robot-robot* head-on corridor negotiation with refuges or bays. Nobody has compared the families above (reactive, fixed priority, rulebook, bidding, centralised oracle, LLM, MARL) on one physics-based ROS 2 platform with common metrics. The nearest scenario assets are the VMAS `give_way` scenario (a corridor with one asymmetric opening) [@vmasgiveway], MARLIN's "single-slot" and "two-slot" corridors [@marlin2024], the doorway, hallway and intersection "social mini-games" [@chandra2026social], and width-1 corridors in grid MAPF [@experience2024narrow]. None of these combines continuous nonholonomic reversing, choice of bay, asymmetric urgency or cost, communication impairment, and repeated-encounter fairness. That combination is the opening for this project (Section 6).

## 2. Scope, method and key distinctions

**Search and verification.** Candidate papers were collected from the topics in the brief, from the reference lists of the recent surveys [@chandra2026social; @mirsky2024conflict; @francis2025principles; @fragapane2021planning; @stern2019mapf], and by forward search on Crossref and OpenAlex. Each candidate was confirmed by DOI resolution, an exact-title match in Crossref or OpenAlex, an arXiv ID lookup, or by fetching its stable URL. Remembered references that could not be confirmed were dropped. About 20 works were read in full or in large part (Section 4). Every row of the comparison table and every number quoted in the text was then rechecked against the full text wherever an open copy exists (Section 12). The remaining works are summarised from their abstracts.

The same words mean different things in different communities, so the review uses five distinctions throughout:

| Distinction | Meaning in this review | Why it matters for the pull-in-bay study |
|---|---|---|
| **Collision avoidance vs. deadlock resolution** | Collision avoidance keeps robots apart (safety). Deadlock or livelock resolution makes sure they eventually reach their goals (liveness). | Safe reactive controllers such as ORCA, CBFs and the ROS 2 Nav2 local planners can be perfectly safe and still deadlock in a one-lane corridor [@grover2023before; @dergachev2021distributed]. |
| **Pairwise corridor negotiation vs. fleet scheduling** | Pairwise negotiation is a local, 2–3 robot, often ad hoc decision about who yields. Fleet scheduling is global planning or scheduling of many robots, for example MAPF or AGV traffic managers. | The canonical scenario is local; its 3+ robot and T-junction variants move towards fleet scheduling. |
| **Guarantees vs. empirical performance** | Proofs of safety, liveness or deadlock-freedom under stated assumptions, versus measured success rates and delays. | Rulebooks and bidding are easy to prove safe given a central lock, but liveness under packet loss needs care [@mannucci2019provably]. |
| **Centralised vs. decentralised** | One planner or authority (Open-RMF, VDA 5050 master control, MAPF oracle) versus robots that decide among themselves. | The centralised oracle gives an upper bound on solution quality; the decentralised policies are the object of study. |
| **Human-robot vs. robot-robot right-of-way** | Social navigation optimises comfort and legibility for people; robot-robot right-of-way can rely on explicit messages, shared rules and truthful (or strategic) cost reporting. | Human-robot corridor studies [@pacchierotti2006evaluation; @goahead2015] supply passing-distance and signalling norms, but robots can negotiate explicitly, which humans in corridors cannot. |

## 3. Taxonomy and historical progression

### 3.1 Taxonomy

| Family | Decision locus | Communication | Typical guarantee | Representative works |
|---|---|---|---|---|
| A. Reactive collision avoidance | each robot | none / state broadcast | safety (often), no liveness | VO/RVO/ORCA [@fiorini1998motion; @vandenberg2008rvo; @vandenberg2011orca], BVC [@zhou2017fast], CBF [@wang2017safety], CADRL [@chen2017cadrl] |
| B. Traffic rules and fixed priority | shared rule set | optional | safety; liveness under assumptions | [@kato1992coordinating; @asama1991collision; @bennewitz2002finding; @vandenberg2005prioritized] |
| C. Zone control / resource reservation | central or distributed lock manager | required | deadlock avoidance (Petri nets, graphs) | [@fanti2002event; @reveliotis2000conflict; @yeh1998deadlock; @geozone2023; @hiertraffic2023] |
| D. Centralised planning / MAPF | central solver | required | optimal / bounded-suboptimal / complete | [@sharon2015cbs; @barer2014suboptimal; @okumura2022pibt; @okumura2023lacam; @li2021lifelong] |
| E. Robust plan execution | central supervisor | required, may be lossy | safety + liveness under delay/loss | [@cap2016provably; @honig2019persistent; @pecora2018loosely; @mannucci2019provably; @mannucci2021provably] |
| F. Explicit negotiation, auctions, mechanisms | agents (± auctioneer) | required | efficiency / incentive compatibility | [@smith1980contract; @gerkey2002sold; @dias2006market; @gautier2022negotiated; @azarm1997conflict; @purwin2008theory] |
| G. Game-theoretic navigation | each agent (equilibrium) | none or intent sharing | liveness under game assumptions | [@chandra2025deadlock; @fisac2019hierarchical; @schwarting2019social] |
| H. Learning (MARL, learned communication) | learned policies | none / learned | empirical | [@sartoretti2019primal; @long2018towards; @bettini2023heterogeneous; @park2023hallucination] |
| I. LLM-mediated negotiation | language agents (± low-level controller) | natural language | empirical | [@mandi2024roco; @garg2024llm; @gamechat2025; @marlin2024] |

### 3.2 Historical progression

- **1991–2001: traffic rules and decoupled priorities.** Early mobile-robot work borrowed road-traffic ideas such as traffic rules, communication of intent and right-of-way. Examples are rule-plus-communication collision avoidance [@asama1991collision], robot traffic rules [@kato1992coordinating] and decentralised negotiation of motion priorities [@azarm1997conflict]. Jäger and Nebel exchanged planned trajectories on proximity, inserted idle times, explicitly *detected* deadlocks and asked planners to replan in turn [@jager2001decentralized]. That is the basic template for "detect, then negotiate". Prioritised and decoupled planning was formalised in [@bennewitz2002finding; @vandenberg2005prioritized].
- **1998–2010: AGV zone control and market-based robotics.** Manufacturing research treated guide-path segments as shared resources and avoided deadlock with Petri nets and graph-theoretic tests [@yeh1998deadlock; @reveliotis2000conflict; @fanti2002event]; the AMR-intralogistics context is reviewed in [@fragapane2021planning]. In parallel, multi-robot task allocation adopted Contract Net and auctions [@smith1980contract; @gerkey2002sold; @dias2006market].
- **2008–2018: reciprocal collision avoidance and formal fleet coordination.** RVO, ORCA and HRVO [@vandenberg2008rvo; @vandenberg2011orca; @snape2011hybrid; @alonsomora2013optimal], BVC [@zhou2017fast] and barrier certificates [@wang2017safety] made decentralised *safety* cheap but left *liveness* open. Prioritised planning gained completeness results for "well-formed infrastructures" [@cap2015prioritized], and execution-time guarantees appeared [@cap2016provably; @pecora2018loosely].
- **2015–present: MAPF at scale.** CBS and ECBS [@sharon2015cbs; @barer2014suboptimal], PIBT and LaCAM [@okumura2022pibt; @okumura2023lacam], lifelong and windowed MAPF [@li2021lifelong] and standard benchmarks [@stern2019mapf] made the centralised oracle practical. Robust and kinodynamic execution followed [@honig2019persistent; @kottinger2022conflict; @dbecbs2025].
- **2016–present: deep RL and learned communication.** CADRL and GA3C-CADRL [@chen2017cadrl; @everett2018motion], end-to-end decentralised policies [@long2018towards], learned MAPF [@sartoretti2019primal; @li2020graph], and learned communication [@foerster2016learning; @das2019tarmac].
- **2022–present: "social mini-games" and deadlock theory.** Formal characterisation of CBF deadlock [@grover2023before], game-theoretic liveness in doorways and hallways [@chandra2025deadlock], and a 2025–26 taxonomy of the area [@chandra2026social].
- **2023–present: LLM agents.** Dialogue-based multi-robot planning [@mandi2024roco; @kannan2024smart; @chen2024scalable], foundation models as deadlock resolvers [@garg2024llm], LLM-negotiated priority in doorways [@gamechat2025] and LLM negotiation guiding MARL on TurtleBot3s [@marlin2024].

## 4. Per-theme synthesis

### 4.1 Deadlock and livelock in narrow passages

**Why reactive controllers deadlock.** Grover, Liu and Sycara study the closed-loop dynamics of multi-robot CBF quadratic-program controllers [@grover2023before]. They show that geometric *symmetry* of initial conditions and goals necessarily leads to deadlock, that heterogeneous controller parameters can help, and they use duality theory to characterise configurations "during" deadlock and design controllers to escape it "after". The escape strategy is validated in simulation with two and three robots and on Khepera-IV robots (the IJRR paper extends the authors' DARS 2020 conference version, which is therefore not cited separately). The head-on corridor is the extreme symmetric case: without asymmetry injected by rules, priorities, perturbations [@pseudogoal2024] or communication, a CBF or ORCA controller has no reason to give way. Zheng et al. reach a similar conclusion for ORCA-like QPs on nonholonomic robots. They add "masked velocities" (MCCA), a lightweight form of cooperation that propagates through the team, and handle heading oscillation for differential-drive robots, which is relevant to TurtleBot3 [@zheng2023deadlock].

**Detect-then-coordinate.** Jäger and Nebel detect deadlock and trigger sequential replanning [@jager2001decentralized]. Dergachev and Yakovlev run ORCA by default and, once a deadlock is detected, form a *locally confined MAPF* instance among the robots involved, solved with Push-and-Rotate or ECBS. In maps with tight passages this raised success rates from 10–15% to 95–99% "in certain cases" (their Section I; e.g. 99% vs. just over 70% for the ORCA baseline with 40 agents in one map) [@dergachev2021distributed]. This hybrid is an important baseline because it mirrors the planned protocol: robots drive reactively until a conflict is detected, then switch to an explicit decision procedure.

**Delays, disturbances and communication faults.** Čáp, Gregoire and Frazzoli prove that a simple execution rule, which respects the planned precedence of robots at shared regions, is safe *and* deadlock-free even when robots are delayed by disturbances such as passing humans. Naive liveness-preserving rules scale poorly with disturbance intensity [@cap2016provably]. Mannucci et al. drop the perfect-communication assumption from a centralised loosely coupled coordinator. With delays only, safety is guaranteed. With packet loss, the probability of unsafety is bounded as a function of the channel model [@mannucci2019provably]. They later add liveness with online goal posting and heterogeneous robots, "without hand-coded rules [or] fixed robot priorities" [@mannucci2021provably]. Matos et al. present a TEA*-based AGV system that tolerates zones with no network coverage [@commfail2021]. Together these works make **latency and packet loss** a first-class variable, and show that it must be modelled explicitly instead of hoping the protocol is robust. Communication in multi-robot systems more broadly is reviewed in [@gielis2022critical].

### 4.2 Right-of-way, AGV traffic rules and industrial frameworks

**Zone control.** Classical AGV systems split the guide path into zones that one vehicle at a time may hold. Deadlocks are predicted and avoided by checking for cyclic waits [@yeh1998deadlock; @reveliotis2000conflict; @fanti2002event]. Lee et al. note that this work assumes "sufficient space between nodes and links". They partition zones using vehicle geometry and guide-path topology, which matters for physically wide robots in narrow aisles [@geozone2023]. Pratissoli et al. describe a three-layer (topological, path, roadmap) traffic manager with a deadlock-prevention coordination step for real industrial layouts [@hiertraffic2023]. A one-lane corridor with bays maps directly onto zone control: each corridor segment and each bay is a resource. The bays work like the "storage" or "parking" nodes used in AGV deadlock-avoidance proofs and in MAPD "standby" locations [@yamauchi2022standby]. A review of AMR planning and control for intralogistics gives the industrial context [@fragapane2021planning].

**Industrial frameworks and standards.**

- *Open-RMF* is the ROS 2 ecosystem's multi-fleet coordination framework [@openrmf; @ros2multirobotbook]. Its `rmf_traffic` package "implements the algorithms and data structures that are used for scheduling and negotiating mobile robot traffic between multiple agents" [@rmftraffic]. Fleet adapters publish intended itineraries to a shared schedule database. When conflicts are detected, the fleets involved negotiate by exchanging alternative proposals. This is the closest deployed analogue of the planned "rule-based" and "bidding" protocols, and the **natural industrial comparator** to discuss (and possibly integrate) in the ROS 2 Jazzy stack.
- *VDA 5050* standardises the interface between a central master control and AGVs (orders as node/edge graphs, state messages) [@vda5050]. Traffic management and conflict resolution stay with the master control, so under VDA 5050 the pull-in-bay decision is centralised. This is the "centralised oracle" family.
- *MassRobotics AMR Interoperability Standard* specifies status and location reporting so that robots from different vendors can share a facility [@massrobotics]. It supports *awareness*, but contains no negotiation protocol.
- *ISO 3691-4:2023* covers safety requirements and verification for driverless industrial trucks and their systems [@iso36914]. Its contents were not consulted for this review (paywalled). It should still be checked for the safety-related requirements on clearances and speed that the min-clearance metric and the reversing manoeuvre will have to respect in any real deployment.

### 4.3 MAPF and priority-based planning as the centralised baseline

MAPF offers the strongest *centralised oracle*. Variants and benchmark maps are standardised in [@stern2019mapf]. CBS is optimal [@sharon2015cbs]; ECBS and EECBS are bounded-suboptimal [@barer2014suboptimal]. Prioritised planning is fast but incomplete in general [@vandenberg2005prioritized; @cap2015prioritized]. PIBT adds **priority inheritance with backtracking**: a high-priority agent that is blocked passes its priority to the blocker, which must move, and backtracking guarantees reachability in biconnected graphs [@okumura2022pibt]. LaCAM builds a complete search on top of PIBT-style successor generation [@okumura2023lacam]. Lifelong and windowed MAPF (RHCR) resolves conflicts only within a rolling horizon [@li2021lifelong]. MAPF can also be posed as a combinatorial auction [@amir2015mapfauction], a bridge to Section 4.5.

**Narrow corridors.** Moan et al. target width-1 corridors ("doorways") in houses and offices. Their conflict-resolution strategies cut waiting steps per robot by up to 94% compared with earlier experience-based methods [@experience2024narrow]. Singh et al. schedule nodes to robots for lifelong operation in long narrow corridors, with an explicit deadlock-detection-and-resolution step [@nodetorobot2023]. Pertzovsky et al.'s MACGA has agents build "corridors" towards their goals and *evacuate* other agents out of them, an explicit move-aside primitive analogous to pulling into a bay [@macga2025]. McBeth et al. use topological guidance for congested environments with many narrow passages [@topoguide2023].

**Kinodynamics and reversing.** Grid MAPF ignores orientation, acceleration and reversing cost. Persistent execution uses an action-dependency graph to tolerate slow-downs [@honig2019persistent]. Kinodynamic CBS [@kottinger2022conflict], CL-MAPF for car-like robots [@wen2022clmapf] and the discontinuity-bounded db-ECBS [@dbecbs2025] plan directly in continuous state spaces. For TurtleBot3 (differential drive, symmetric forward and reverse kinematics, but rear-facing sensing limited to the 360° LDS) the main gap is that **reversing is rarely priced differently from driving forward**. An oracle for this study should charge extra for reverse motion and turning.

### 4.4 Decentralised collision avoidance and its failure in corridors

Velocity obstacles [@fiorini1998motion], RVO [@vandenberg2008rvo], ORCA [@vandenberg2011orca], HRVO, which targets the reciprocal "dance" [@snape2011hybrid], and their nonholonomic and kinodynamic extensions [@alonsomora2013optimal] all share the same structure. Each agent solves a local optimisation that is symmetric in the agents. In a corridor that is too narrow to pass, the feasible velocity set collapses to "stop", which is a stable deadlock [@dergachev2021distributed; @zheng2023deadlock]. BVC planning [@zhou2017fast] and barrier certificates [@wang2017safety] guarantee collision avoidance, but CBF-based liveness requires additional mechanisms [@grover2023before]. The dynamic window approach [@fox1997dwa], which underlies common ROS local planners [@macenski2020marathon], behaves the same way. Learned reactive policies (CADRL and GA3C-CADRL [@chen2017cadrl; @everett2018motion], end-to-end sensor-level policies [@long2018towards]) can learn conventions such as passing on the right [@chen2017socially]. They are trained on open-space crossings, though, and do not reason about reversing into a refuge. Park et al. say directly that standard navigation stacks, when two robots meet in a narrow hallway, "may either turn around to find an alternative route or collide". Their PHHP method learns where to *hallucinate* virtual obstacles so that unmodified planners pass smoothly, tested on physical robots without explicit communication [@park2023hallucination].

### 4.5 Explicit negotiation protocols, games and norms

**Protocols.** Contract Net [@smith1980contract] and auction-based coordination [@gerkey2002sold; @dias2006market] were built for *task* allocation, but they carry over to *right-of-way* allocation, where the resource being auctioned is the corridor. Azarm and Schmidt negotiate motion priorities among robots in local conflicts using online motion planning [@azarm1997conflict], and Purwin et al. negotiate reserved regions among decentralised agents [@purwin2008theory]. Automated negotiation [@jennings2001automated] and argumentation-based negotiation [@rahwan2003argumentation] provide richer protocols, where agents exchange reasons such as "I carry an urgent payload" or "my refuge is 0.5 m behind me". These map onto the ordered YAML rulebook.

**Games and mechanism design.** Two robots competing for a single-lane corridor play a *Chicken*/Hawk–Dove game [@maynardsmith1973logic]: mutual "hawk" (both advance) leads to deadlock or collision, and each prefers the other to yield. With divisible delay costs this is a bargaining problem [@nash1950bargaining]. In alternating-offers bargaining a discount factor, which here means the cost of waiting, determines the split [@rubinstein1982perfect]. **Cost-based bidding** ("lower bid yields") is a sealed-bid mechanism. If each robot's bid is its private cost of yielding, truthful bidding is not automatically incentive-compatible: each robot gains by over-reporting its cost. Second-price/VCG-style payments [@vickrey1961counterspeculation; @nisan2001algorithmic] or credit ledgers are the textbook fix. Gautier et al. design exactly such an auction for *non-cooperative* MAPF, so that rational, self-interested robots from different owners reach goals while system cost is minimised [@gautier2022negotiated]. Intersection-management auctions [@carlino2013auction] are a close road analogue. For fleets from the same owner, truthfulness is assumed by design; for **heterogeneous or multi-vendor fleets** (the MassRobotics use case [@massrobotics]) it is not.

**Social conventions.** Social laws such as "keep right" or "the robot nearer to a refuge yields" can be designed offline so that conflicts never arise [@shoham1995social]. They are also learned implicitly by RL [@chen2017socially] and are part of human driving codes [@highwaycode]. The ordered rulebook (urgency > first-in-corridor > closest refuge behind > lower ID) is a lexicographic social law. Its safety follows from the central lock, and its *liveness* depends on the rules producing a strict total order and on both robots seeing the same facts, which latency or packet loss can break.

### 4.6 Game-theoretic "social mini-games"

Chandra et al. define *social mini-games*: doorways, narrow hallways and corridor intersections where agents compete for space. They pose these as non-cooperative, non-communicative, partially observable receding-horizon games. A minimally invasive perturbation, based on discrete-time CBFs, pushes the joint state into "liveness sets" [@chandra2025deadlock]. They test on F1/10 cars, a Clearpath Jackal and a Boston Dynamics Spot in doorway, hallway and intersection scenarios. Metrics are success rate, collision rate, stop time, change in velocity, path deviation, time-to-goal and flow rate. A follow-up survey and taxonomy reviews SMG solvers across MAPF, MARL, game-theoretic and optimisation communities, and notes that publications "make different assumptions" that prevent comparison [@chandra2026social]. Related work includes bilevel non-cooperative social navigation [@chandra2023decentralized], opinion-dynamics symmetry breaking [@alghamdi2025opinion] and pseudo-goal perturbation [@pseudogoal2024]. Game-theoretic planners from driving, including hierarchical games [@fisac2019hierarchical] and social value orientation [@schwarting2019social], provide solvers for richer asymmetric-cost versions.

### 4.7 Learning approaches

MARL baselines suitable for the study include MAPPO [@yu2022mappo], with sequential social dilemmas [@leibo2017multi] as a lens on yielding as cooperation. Learned communication comes in several forms: DIAL and RIAL [@foerster2016learning], TarMAC [@das2019tarmac] and GNN-based MAPF [@li2020graph]. VMAS provides vectorised 2-D multi-robot environments [@bettini2022vmas], including `give_way`: two agents in a narrow corridor must swap places, and an asymmetric opening in the middle fits only one agent, so "the optimal policy is for one agent to give way to the other" [@vmasgiveway]. the scenario documentation notes that it "requires heterogeneous behaviour", which is the motivation for heterogeneous MARL such as HetGPPO [@bettini2023heterogeneous]. PRIMAL learns decentralised MAPF policies by combining reinforcement and imitation learning [@sartoretti2019primal]. Learned approaches remain empirical; none of these works gives liveness guarantees, and sim-to-real transfer of a give-way policy to a ROS 2 robot is rarely shown. MARLIN is the exception (Section 4.8).

### 4.8 LLM-based multi-robot negotiation and coordination (2023 onward)

- **RoCo** uses one LLM agent per robot arm. The agents talk to each other to agree on sub-tasks and waypoints, and environment feedback (for example collision checks) is fed back in-context. RoCoBench has 6 tasks, and GPT-4 reaches 86.7% success on a path-planning task within 5 attempts [@mandi2024roco]. The setting is manipulation, not navigation, but the dialogue-and-feedback loop is directly reusable.
- **Task-level planners**: SMART-LLM [@kannan2024smart], centralised vs. decentralised LLM planning architectures [@chen2024scalable] and a 2025–26 survey of LLMs for multi-robot systems [@li2025llmmrs].
- **Garg et al.** use LLMs and VLMs as *high-level deadlock resolvers* above a learned low-level controller. When robots stall, the foundation model picks a leader and waypoints. Tests cover 5–50 agents in "Room" and "Maze" environments with GPT-4/4o and Claude-3 models; metrics are reach rate, number of interventions, time, tokens and distance travelled [@garg2024llm].
- **GameChat** has agents in symmetric doorways or intersections *talk* in natural language (gpt-4o-mini) to establish priority, for example "an emergency that threatens many lives takes precedence", and then run a game-theoretic controller so that the higher-priority agent passes first [@gamechat2025]. This is an LLM version of the "urgency" rule.
- **MARLIN** lets robots negotiate actions through an LLM (Llama 3.1 8B) early in MARL training, then hands over to the learned policy. The scenarios are corridors with *one or two side slots*: "Asymmetrical Two Slot Corridor", "Single Slot Corridor", "Symmetrical Two Slot Corridor" and "Maze-Like Corridor". These were validated on **two TurtleBot3 Waffle robots running ROS 2 Humble** [@marlin2024]. It is the closest prior physical setup to the present study. However, it uses grid-like moves, evaluates against MARL and LLM-only baselines rather than rules, bidding or an oracle, and does not vary latency, urgency or fairness.
- **Negotiation in language** in general: LLM-stakeholder negotiation games show that LLMs can bargain, but can also act maliciously or be manipulated [@abdelnabi2024cooperation]. That last point matters if LLM negotiation is used between robots from different owners.

### 4.9 Social navigation benchmarks and evaluation protocols

Francis et al. give consensus principles and guidelines for evaluating social navigation: metrics, scenarios, benchmarks, datasets and simulators [@francis2025principles]. Other contributions include SocNavBench [@biswas2022socnavbench], SocialGym 2.0, a simulator for multi-robot learning and navigation [@socialgym2aaai], Arena-Rosnav, which builds on Flatland [@kastner2021arena], BARN [@xiao2022barn], and scenario complexity characterisation [@stratton2024complexity]. Surveys: [@mavrogiannis2023core; @mirsky2024conflict]. Mirsky et al.'s conflict-avoidance survey is the most relevant, because it organises the literature around the very corridor and doorway conflicts this study targets [@mirsky2024conflict]. Human-robot corridor-passing studies give useful priors for *robot-robot* behaviour: preferred passing distance and early lateral shifts [@pacchierotti2006evaluation], resolving a narrow-passage deadlock with a person by waiting in a non-disturbing position or queueing [@goahead2015], and making intent legible with light or gaze signals [@fernandez2018passive; @hart2020using]. Pérez-D'Arpino et al. train RL navigation in constrained pedestrian environments, including doorways [@perezdarpino2021robot]. These benchmarks are *human-robot*; none ships a robot-robot head-on corridor-with-bays scenario with negotiation-specific metrics such as reverse distance or messages exchanged.

### 4.10 Road-traffic analogues

The UK Highway Code's single-track-road rule describes the canonical scenario directly: "pull into a passing place on your left, or wait opposite a passing place to let the other vehicle pass" [@highwaycode]. Youssef et al. survey 243 UK drivers on narrow-passage give-way decisions and on how they perceive communication cues [@narrowpassageuk2023]. Li et al. propose AV-to-human-driver negotiation via in-vehicle displays on bottleneck roads [@avmvbottleneck2023]. Baumann et al. design a V2V cooperative bottleneck protocol (e.g. at a roadblock). Its main challenge in dense traffic is *acceptance and fairness*: limiting the waiting imposed on any one user by alternating priority by queue position [@bottleneckiv2023]. That supports including **fairness** as a primary metric. So do intersection-management protocols, both reservation-based [@dresner2008multiagent] and delay- and packet-loss-tolerant [@delaytolerant2019], and surveys of CAV coordination [@hafner2022survey].

### 4.11 Simulation tooling

| Tool | Fidelity | ROS 2 | Multi-robot corridor use in literature | Notes for this study |
|---|---|---|---|---|
| Gazebo (Harmonic) [@koenig2004gazebo; @gazebosim] | 3-D physics, sensors | native (`ros_gz`) | common for TurtleBot/Jackal studies | chosen platform; TurtleBot3 Waffle models available [@turtlebot3] |
| Stage [@vaughan2008stage] | 2.5-D kinematic | ROS 1 legacy | many early MARL navigation papers [@long2018towards] | fast, large teams |
| Flatland [@flatland] | 2-D physics | ROS 1, Arena-Rosnav ports | Arena-Rosnav / Arena-Bench [@kastner2021arena] | fast DRL training |
| Unity / ML-Agents [@juliani2018unity] | game engine | via bridges | social-navigation studies | human crowds, photo-realism |
| Isaac Sim / Isaac Lab (Orbit) [@isaacsim; @mittal2023orbit] | GPU physics, RTX | ROS 2 bridge | growing MARL use | already used in this repo for other robots |
| VMAS [@bettini2022vmas] | vectorised 2-D | none (PyTorch) | `give_way`, `passage`, `joint_passage` scenarios [@vmasgiveway] | ideal for MARL pre-training of yield policies |
| Robotarium [@pickem2017robotarium] | real swarm testbed | remote API | CBF deadlock studies | remote hardware validation |
| ROS 2 / Nav2 [@macenski2020marathon] | stack | — | most physical studies | provides DWB/MPPI local planners, which are the "reactive" baseline |

**Is there a standard robot-robot corridor-negotiation suite?** No. Existing suites cover (i) grid MAPF maps [@stern2019mapf], (ii) human-robot social navigation [@francis2025principles; @biswas2022socnavbench; @socialgym2aaai], (iii) single-robot constrained navigation [@xiao2022barn], and (iv) MARL toy scenarios [@vmasgiveway]. Robot-robot bottleneck scenarios exist only as bespoke scenes inside individual papers [@chandra2025deadlock; @park2023hallucination; @marlin2024; @gamechat2025]. Releasing the parameterised Gazebo Harmonic scenario set (bay position, bay count, T-junction, doorway, and so on) as an open benchmark would be a contribution in its own right.

## 5. Comparison of the closest ~20 works

"Checked against" says what each row was verified against in the October 2026 integrity check (Section 12). "Full text" means the cells were checked against the paper body. Where only an arXiv copy was open, the arXiv version of the published paper was used. "Abstract only (paywalled)" rows rest on the abstract and metadata.

| Reference | Scenario | #Robots | Comms assumption | Decision mechanism | Sim / real platform | Metrics | Limitations w.r.t. pull-in-bay study | Checked against |
|---|---|---|---|---|---|---|---|---|
| [@marlin2024] | single-/two-slot corridors, maze-like corridor | 2 | LLM negotiation messages | LLM negotiation guiding MARL | sim + 2× TurtleBot3 Waffle, ROS 2 Humble | performance metric (their Alg. 1) over training episodes | discrete moves; no rule/bidding/oracle baselines; no latency/urgency/fairness study | full text (arXiv) |
| [@gamechat2025] | symmetric doorway, intersection | 2 (extension to >2 shown) | natural language between LLM agents | LLM dialogue sets priority; game-theoretic low-level control | simulation | time for all agents to reach goals; rate at which the higher-priority agent goes first (50%→100%) | LLM latency/cost not stress-tested; no reversing into refuge | full text (arXiv version of the published paper) |
| [@garg2024llm] | rooms, mazes (obstacle deadlocks) | 5–50 | connected MRS + central high-level planner | LLM/VLM leader + waypoint selection | simulation | goal-reaching rate, no. of high-level interventions, time per intervention, tokens, distance travelled | centralised high-level planner; not a pairwise protocol | full text (arXiv) |
| [@chandra2025deadlock] | doorway, hallway, corridor intersection | 2+ | none (non-communicative) | DT-CBF perturbation onto liveness sets (game-theoretic) | sim + F1/10, Jackal, Spot | success, collision rate, stop time, Δv, path deviation, time-to-goal, flow rate | assumes passing is possible by slowing; no reversing/bay choice | full text (arXiv version of the published paper) |
| [@chandra2026social] | social mini-games taxonomy | — | varies | survey | — | catalogue of metrics | survey; motivates common benchmark | full text (arXiv version of the published paper) |
| [@grover2023before] | symmetric multi-robot CBF configurations | 2–N | state sharing for CBF | CBF-QP analysis; deadlock escape controller | sim (2–3 robots) + Khepera-IV robots | deadlock characterisation, convergence | theory for holonomic/double-integrator models; no corridor geometry | full text (arXiv version of the published paper) |
| [@dergachev2021distributed] | tight passages, confined spaces | multi-agent | local, only when deadlocked | ORCA + locally confined MAPF (Push&Rotate / ECBS) | simulation | success rate, flowtime | holonomic discs; grid abstraction for local MAPF | full text (arXiv version of the published paper) |
| [@zheng2023deadlock] | crowded swaps, narrow spaces | many | neighbour velocity sharing | QP with masked cooperative velocities (MCCA) | simulation (differential drive) | simulation comparison (Sec. VI) | no explicit refuge reasoning or fairness | full text (arXiv) |
| [@park2023hallucination] | two robots pass in a 1.6 m hallway (65 cm-wide robots) | 2 | none | learned virtual-obstacle ("hallucination") placement for a standard planner | sim + 2 physical BWIBots | Δt vs. single robot, P(collision), P(failure); vs. right-lane-following, NH-ORCA, halting | assumes hallway wide enough to squeeze past; no bays | full text (arXiv version of the published paper) |
| [@cap2016provably] | empty hall, office corridor, warehouse (well-formed infrastructures) | many | central plan, precedence at execution | precedence-preserving execution rule | simulation | delay vs. disturbance intensity | needs global plan; no negotiation | full text (arXiv version of the published paper) |
| [@mannucci2019provably] | industrial fleets with lossy network | many | delays + packet loss | central loosely coupled coordinator | not checked | safety probability, performance | centralised; critical-section heuristics | abstract only (paywalled) |
| [@mannucci2021provably] | heterogeneous fleet, online goals | ≤ 40 | central | loosely coupled supervisory control | simulated robots in benchmark scenarios and a real-mine scenario | safety/liveness proofs, efficiency | centralised; no pairwise incentive model | full text (open-access publisher) |
| [@hiertraffic2023] | real factory/warehouse layout | fleet | central | three-layer traffic manager, deadlock prevention | simulation of a real plant layout | deadlock-freedom, performance in simulation | AGV roadmap; no bidding/fairness | full text (open-access publisher) |
| [@geozone2023] | irregular AGV guide paths | fleet | zone controller | geometry-aware zone control | simulation | delivery performance (58–85% better than state-of-the-art baselines) | central; no robot-level negotiation | full text (open-access publisher) |
| [@experience2024narrow] | width-1 corridors / doorways (grid) | hundreds | central | experience-based MAPF + conflict-resolution strategies | grid simulation | waiting steps/robot (up to 94% fewer), path cost (up to 71% closer to optimal decoupled) | grid; no kinodynamics or reversing cost | full text (RSS proceedings) |
| [@nodetorobot2023] | long narrow corridors, lifelong | many | central | node-to-robot scheduling + deadlock detection/resolution | simulation | conflict-freedom, throughput | graph abstraction | abstract only (paywalled) |
| [@macga2025] | dense MAPF grids incl. mazes | many | central | corridor building + evacuation (+PIBT) | grid benchmarks [@stern2019mapf] | success rate, runtime, makespan | grid; evacuation ignores motion cost | full text (IJCAI proceedings) |
| [@okumura2022pibt] | MAPF/MAPD grids, warehouses | 100s | central or local priority | priority inheritance with backtracking | sim + real-robot demo | runtime, SoC/makespan | discrete; priority inheritance ≠ negotiation | full text (arXiv version of the published paper) |
| [@jager2001decentralized] | independently planned trajectories | several | local exchange on proximity | trajectory exchange, idle-time insertion, deadlock detection + replanning | simulation | deadlock resolution, delays | early; no formal liveness | abstract only (paywalled) |
| [@bottleneckiv2023] | road bottleneck (roadblock), mixed traffic | many vehicles | V2V | cooperative give-way negotiation by queue position | OCTANE2 traffic simulation | waiting times, throughput, acceptance | road geometry; no reversing | full text (arXiv version of the published paper) |
| [@rmftraffic] | multi-fleet buildings | fleet | schedule DB + negotiation | itinerary proposals/negotiation | deployed open source (ROS 2) | — (software) | no published benchmark of negotiation quality | full text (README) |
| [@vmasgiveway] | corridor with one asymmetric opening | 2 | none (obs only) | learned (MARL) | VMAS 2-D | reward / success | 2-D point robots; no comms impairments | full text (scenario source and docs) |

## 6. Research gaps and opportunities: positioning the pull-in-bay study

**Gap 1 — No common benchmark or metric set for robot-robot head-on negotiation with refuges.** Corridor and doorway conflicts appear in MAPF grids [@experience2024narrow; @macga2025], social mini-games [@chandra2025deadlock], MARL toy scenarios [@vmasgiveway] and MARLIN's slotted corridors [@marlin2024], but every paper builds its own scene and metrics. Surveys explicitly ask for comparable assumptions and benchmarks [@chandra2026social; @francis2025principles; @stratton2024complexity]. *Opportunity:* release a parameterised Gazebo Harmonic + ROS 2 Jazzy scenario suite: bay side and position, number of bays, bay depth versus robot footprint, T-junctions, doorways, robot count, and heterogeneous footprints, speeds and payloads. Pair it with a fixed metric set (Section 8) and a seeded protocol.

**Gap 2 — No head-to-head comparison of decision mechanisms under the same physics and communication model.** Each family is usually compared only against reactive baselines or its own ablations. Rules [@kato1992coordinating; @shoham1995social], auctions and bidding [@gerkey2002sold; @gautier2022negotiated], centralised MAPF or zone control [@okumura2022pibt; @hiertraffic2023], industrial negotiation (`rmf_traffic`) [@rmftraffic], LLM dialogue [@gamechat2025; @garg2024llm] and MARL [@bettini2023heterogeneous] have never been evaluated side by side. Latency and packet loss are modelled in centralised coordinators [@mannucci2019provably; @commfail2021; @delaytolerant2019] but not in pairwise negotiation protocols. *Opportunity:* the five planned policies, with a common message layer that injects delay and loss, give the first controlled comparison. The **price of decentralisation** (oracle vs. negotiation) and the **price of communication impairment** can then be reported as ratios.

**Gap 3 — Refuge selection with reversing cost, asymmetric private costs, and incentives and fairness over repeated encounters.** MAPF and AGV work usually treats a bay as just another node and charges reversing the same as forward motion; kinodynamic MAPF is recent [@kottinger2022conflict; @dbecbs2025]. Game-theoretic SMG work resolves *who goes first* by slowing down, not by *who backs into which bay* [@chandra2025deadlock]. Bidding protocols assume truthful costs, while mechanism design shows that self-interested robots may misreport [@vickrey1961counterspeculation; @nisan2001algorithmic; @gautier2022negotiated]. Fairness across repeated encounters is raised in road bottlenecks [@bottleneckiv2023] but rarely measured for robots. *Opportunity:* model cost-to-yield explicitly (reverse distance, turning, payload, urgency, battery). Compare truthful versus strategic bidding, with and without VCG-style payments or credit ledgers, and report fairness across encounters with Jain's index [@jain1984fairness].

**Secondary opportunities.** (i) Heterogeneous fleets: different footprints and speeds, and a multi-vendor interoperability story via MassRobotics or VDA 5050 [@massrobotics; @vda5050]. (ii) LLM negotiation as a policy, measured on latency, tokens and robustness to adversarial or "selfish" prompts [@abdelnabi2024cooperation]. (iii) Formal liveness of the rulebook under message loss, in the style of [@cap2016provably; @mannucci2019provably]. (iv) Sim-to-real on TurtleBot3, following the MARLIN hardware precedent [@marlin2024].

## 7. Recommended baselines (literature-backed)

| # | Policy | Literature anchor | Implementation notes |
|---|---|---|---|
| 1 | Reactive / no communication | ORCA, DWA, CBF deadlock [@vandenberg2011orca; @fox1997dwa; @grover2023before] | Nav2 controller (DWB or MPPI) as-is; expect deadlock and oscillation in symmetric cases |
| 1b | Reactive + random/perturbation tie-break | symmetry breaking [@pseudogoal2024; @alghamdi2025opinion] | cheap stronger baseline: random back-off as in Ethernet-style contention |
| 2 | Fixed priority (lower ID yields) | prioritised planning [@bennewitz2002finding; @vandenberg2005prioritized; @cap2015prioritized] | report unfairness explicitly |
| 3 | Ordered rulebook (YAML) | traffic rules and social laws [@kato1992coordinating; @shoham1995social; @highwaycode] | ensure a strict total order; log which rule decided |
| 4 | Cost-based bidding | auctions / market coordination [@gerkey2002sold; @dias2006market; @gautier2022negotiated] | add a strategic-bidder variant and a second-price/credit variant [@vickrey1961counterspeculation] |
| 5 | Centralised oracle | CBS/ECBS/PIBT/LaCAM with kinodynamic post-processing [@sharon2015cbs; @okumura2022pibt; @okumura2023lacam] | grid over corridor + bays; charge extra for reverse moves; gives a lower bound on makespan and delay |
| 6 | Industrial comparator | Open-RMF `rmf_traffic` negotiation [@rmftraffic] | optional; shows practical relevance |
| 7 | Detect-then-local-MAPF hybrid | [@dergachev2021distributed; @jager2001decentralized] | bridges reactive and centralised |
| 8 | Auctions (multi-robot) | Contract Net, consensus auctions [@smith1980contract; @gerkey2002sold] | for 3+ robots and multiple bays |
| 9 | LLM negotiation | [@gamechat2025; @garg2024llm; @mandi2024roco] | measure decision latency, tokens, failure modes; local LLM (as in [@marlin2024]) vs. API |
| 10 | MARL | MAPPO/HetGPPO in VMAS → Gazebo [@yu2022mappo; @bettini2023heterogeneous; @bettini2022vmas] | pre-train in `give_way`-style scenes [@vmasgiveway] |

## 8. Recommended metrics

| Metric | Definition | Literature support |
|---|---|---|
| Success rate / deadlock rate / livelock rate | episode reaches all goals within timeout; deadlock = no progress for *T* s with zero velocity; livelock = no progress with oscillating motion | [@chandra2025deadlock; @dergachev2021distributed; @grover2023before; @garg2024llm] |
| Time-to-resolve | from conflict detection to the first robot exiting the shared segment | analogous to stop time in [@chandra2025deadlock] |
| Makespan, sum-of-costs / total delay | max and sum of arrival times; delay versus a free-flow single-robot run | [@stern2019mapf; @macga2025] |
| Reverse distance and reverse time | path length driven in reverse; extra turning | new; motivated by kinodynamic MAPF [@kottinger2022conflict; @wen2022clmapf] |
| Collisions and minimum clearance | contacts; minimum footprint-to-footprint distance | [@chandra2025deadlock; @francis2025principles]; clearance norms [@pacchierotti2006evaluation; @iso36914] |
| Path deviation, Δv / smoothness | deviation from nominal path; velocity changes | [@chandra2025deadlock] |
| Messages / bytes exchanged; decision latency | protocol overhead; time from first message to agreement | [@gielis2022critical; @garg2024llm] (tokens) |
| Robustness to latency and loss | metric degradation versus delay and loss rate | [@mannucci2019provably; @delaytolerant2019; @commfail2021] |
| Fairness | Jain's index over per-robot delay across repeated encounters; yield share | [@jain1984fairness; @bottleneckiv2023] |
| Throughput / flow rate (3+ robots) | robots per minute through the corridor | [@chandra2025deadlock; @li2021lifelong] |
| Price of decentralisation | metric(policy) / metric(oracle) | standard in MAPF/coordination comparisons [@cap2015prioritized] |

Report means with 95% confidence intervals over seeded trials and paired comparisons across policies on identical seeds, following the evaluation guidance in [@francis2025principles].

## 9. Recommended scenario matrix

| Factor | Levels | Motivation |
|---|---|---|
| Bay position / side | centre vs. near one end; left vs. right vs. both | asymmetric opening in [@vmasgiveway]; "passing place on your left" [@highwaycode]; MARLIN asymmetric vs. symmetric slots [@marlin2024] |
| Number of bays | 0 (deadlock control), 1, 2, *k* | multiple refuges change who has the "closest refuge behind" |
| Arrival timing | simultaneous vs. staggered entry | first-in-corridor rule; precedence in [@cap2016provably] |
| Asymmetric speed / payload / urgency | equal; 2× speed; loaded vs. empty; urgent flag | GameChat priorities [@gamechat2025]; heterogeneous MARL [@bettini2023heterogeneous] |
| Communication | ideal; 50–500 ms latency; 1–30% loss; partitions | [@mannucci2019provably; @commfail2021; @delaytolerant2019] |
| Robot count | 2, 3, 4+ (convoys, same-direction followers) | fleet scheduling regime [@li2021lifelong; @nodetorobot2023] |
| Topology | straight corridor; T-junction; doorway; corridor intersection | social mini-games [@chandra2025deadlock; @chandra2026social] |
| Heterogeneity | TurtleBot3 Waffle vs. Burger footprints; different controllers; "selfish" agent | non-cooperative MAPF [@gautier2022negotiated]; multi-vendor interoperability [@massrobotics] |
| Repeated encounters | single episode vs. sequences of *N* encounters | fairness [@bottleneckiv2023]; social dilemmas [@leibo2017multi] |

## 10. Candidate publication venues

- **IEEE RA-L** (with ICRA/IROS presentation option) and **ICRA / IROS**: most of the closest work appears here [@park2023hallucination; @chen2024scalable; @kannan2024smart; @mandi2024roco; @dergachev2021distributed].
- **Autonomous Robots** and **IEEE T-RO**: for the full benchmark plus analysis [@chandra2025deadlock; @chandra2026social; @mannucci2021provably].
- **IEEE MRS (Multi-Robot and Multi-Agent Systems Symposium)**: GameChat appeared there [@gamechat2025]; good for an early workshop-length result.
- **AAMAS / IJCAI / AAAI**: for the mechanism-design and negotiation angle (strategic bidding, fairness) [@gautier2022negotiated; @macga2025; @amir2015mapfauction].
- **IEEE CASE / T-ASE**: industrial AGV/AMR framing with Open-RMF/VDA 5050 [@hiertraffic2023; @cap2015prioritized].
- **TAROS / ECMR / Robotics (MDPI)**: smaller European robotics venues (e.g. Matos et al. in *Robotics* [@commfail2021]).
- **ACM THRI / HRI**: only if a human-in-the-loop or legibility component is added [@francis2025principles; @mirsky2024conflict].

## 11. Excluded or unverifiable items

Some frequently remembered titles could not be confirmed with a DOI, arXiv ID or stable page during verification and are **deliberately not cited**. Examples are a claimed "push-and-swap" journal version, a "social-norm emergence" paper and two LLM-MAPF and negotiation-self-play papers. If needed later, they should be re-checked individually before being cited.

## 12. Integrity check (October 2026)

This review went through a second-pass integrity check on 2026-10-14. The steps were:

- Every DOI was re-resolved through Crossref (or doi.org content negotiation) and every arXiv ID through the arXiv API.
- Title, authors, year, venue, volume and pages were compared with the record. Volume, issue and pages were then copied from Crossref into `references.bib`.
- Published versions were searched for every arXiv preprint, using the arXiv journal-ref/DOI fields, Crossref, OpenAlex, Semantic Scholar and DBLP.
- The comparison table, the top-5 list and every quantitative claim were checked against the full text wherever an open copy exists.

**Entries: 205 before, 126 after.**

**arXiv → published replacements.**

- Three entries that were arXiv-only now cite the published version:
  - Zheng & Li → *IEEE RA-L* 9(3):2710–2717 (2024), retitled "MCCA: A Decentralized Method for Collision and Deadlock Avoidance With Nonholonomic Robots".
  - Das et al. (TarMAC) → ICML 2019, PMLR 97:1538–1546.
  - Foerster et al. → NeurIPS 2016.
- Eighteen kept entries carried both a DOI and an arXiv e-print. The arXiv fields were removed and only the published DOI is cited: `bettini2022vmas`, `bettini2023heterogeneous`, `cap2015prioritized`, `cap2016provably`, `chen2017cadrl`, `chen2017socially`, `dergachev2021distributed`, `everett2018motion`, `francis2025principles`, `grover2023before`, `leibo2017multi`, `li2020graph`, `long2018towards`, `mandi2024roco`, `sartoretti2019primal`, `stern2019mapf`, `yamauchi2022standby`, `yu2022mappo`.

**Journal preferred over conference.**

- Grover et al.'s DARS 2020 paper (`grover2020deadlock`) was dropped in favour of its IJRR 2023 journal extension [@grover2023before]. The journal paper itself contains the Khepera-IV experiments.
- For PIBT, the AIJ 2022 journal version [@okumura2022pibt] is cited and not the IJCAI 2019 conference paper. The journal version adds exhaustive one-shot MAPF experiments, a much faster implementation (orders of magnitude lower runtime), further reachability analysis and the real-robot demonstration. The runtime figures and robot demo cited here come from the journal version only.

**arXiv kept (no peer-reviewed version found).**

- MARLIN [@marlin2024]. An AAMAS 2026 paper with the same acronym (DOI 10.65109/rqeq9663) is a different work on reservoir management.
- Garg et al. [@garg2024llm]. A CDC 2024 paper (DOI 10.1109/CDC56724.2024.10886421) on hierarchical deadlock resolution has a different title and author list, so it is not treated as the same work.
- [@chandra2023decentralized], [@alghamdi2025opinion] and the Unity ML-Agents report [@juliani2018unity].
- Jain's fairness index is cited as the 1984 DEC technical report, with the arXiv mirror as e-print [@jain1984fairness].

**Dropped entries (79) and why.**

- *Metadata failure*, 2 entries:
  - `wurman2008coordinating`: the DOI did not resolve (404).
  - `meta2022diplomacy`: corporate author, and the title did not match the Crossref record cleanly.
- *Superseded by a journal version*, 1 entry: `grover2020deadlock`.
- *Trimmed as peripheral to the corridor/bay study*, 76 entries. These are:
  - general MAPF variants and solvers;
  - generic MARL algorithms and frameworks;
  - general LLM-agent surveys;
  - driving game solvers;
  - social-navigation simulators and surveys that are not about corridor passing;
  - tooling papers already covered by documentation URLs;
  - history entries whose point is made by a kept reference.

  Keys: `alami1998multi`, `alonsomora2018cooperative`, `arul2023dsmpepc`, `atzmon2020robust`, `bettini2024benchmarl`, `blumenkamp2020emergence`, `blumenkamp2022framework`, `cap2015complete`, `choi2009consensus`, `cohen2019optimal`, `cyclic2003`, `damani2021primal2`, `dblacam2026`, `decagv2017`, `digani2015ensemble`, `draganjac2016decentralized`, `elhenawy2015intersection`, `everett2021collision`, `fan2020distributed`, `fridovichkeil2020efficient`, `gao2022evaluation`, `gerkey2004formal`, `gregoire2018locally`, `grossman1988traffic`, `gtim2024`, `guo2024llmmulti`, `helbing1995social`, `holtz2022socialgym`, `honig2016mapf`, `hult2016coordination`, `kastner2022arenabench`, `kessler2019cooperative`, `knepper2012pedestrian`, `kruse2013human`, `kurzer2018continuous`, `kurzer2018decentralized`, `lavalle1998optimal`, `leanh2006review`, `lecleach2022algames`, `lewis2017deal`, `li2020new`, `li2021eecbs`, `li2021message`, `li2021pairwise`, `liu2024coherent`, `livenet2024`, `lowe2017maddpg`, `lumelsky1997decentralized`, `ma2017delay`, `ma2017lifelong`, `ma2019searching`, `macenski2022ros2`, `macenski2023desks`, `makoviychuk2021isaacgym`, `pacchierotti2005human`, `pallottino2007decentralized`, `park2023dlsc`, `perille2020benchmarking`, `rashid2018qmix`, `reactive2017deadlock`, `riostorres2017survey`, `sadigh2016planning`, `salzman2020research`, `shalevshwartz2017formal`, `silver2005cooperative`, `sukhbaatar2016learning`, `sun2018courteous`, `tsoi2022sean2`, `vasirani2012market`, `vis2006survey`, `wang1995distributed`, `wang2021game`, `wu2020multi`, `yu2016optimal`, `zhang2024building`, `zhou2017collision`.

**Claims corrected after the full-text check.**

1. *Grover et al.*: the Khepera-IV experiments were attributed to the conference version. They are in the IJRR paper.
2. *Dergachev & Yakovlev*: the "10–15% → 95–99%" success-rate figure is now qualified as "in certain cases", as the paper states. The concrete 40-agent figure was added: 99% vs. just over 70% for the ORCA baseline.
3. *Garg et al.*: the platform was listed as "simulation + robot demo". The paper reports simulation only, so the row now says "simulation". The metrics are now the paper's five: goal-reaching rate, interventions, time per intervention, tokens and distance.
4. *GameChat*:
   - robots: "2+" corrected to "2, with an extension to more than two shown";
   - metrics: replaced with the paper's own, i.e. time for all agents to reach their goals, and the rate at which the higher-priority agent goes first (50% → 100%).
5. *Park et al. (perceptual hallucination)*:
   - metrics replaced with the paper's Δt, P(collision) and P(failure), against right-lane-following, NH-ORCA and halting baselines;
   - setting specified: a 1.6 m hallway with two 65 cm-wide BWIBots.
6. *Čáp et al. 2016*: the row was upgraded from abstract-only to full text. Scenarios are empty hall, office corridor and warehouse; the metric is delay vs. disturbance intensity.
7. *Mannucci et al. 2021*: the platform was "see paper". It is now "simulated benchmark scenarios plus a real-mine scenario, ≤ 40 robots".
8. *Baumann et al. (bottleneck)*: platform specified as OCTANE2 traffic simulation, the decision variable as queue position, and the metrics as waiting times, throughput and acceptance.
9. *Moan et al.*: added the paper's "up to 71% closer to the optimal decoupled path" and "hundreds of robots", alongside the 94% waiting-step reduction.
10. *Lee et al. (geometric zone control)*: added the reported 58–85% performance improvement.
11. *Zheng & Li*: the unverified "success, time" metric cell was replaced, and the paper is now cited as the RA-L version.
12. Several "F" basis labels were replaced with an explicit source: arXiv version, open-access publisher, RSS/IJCAI proceedings, or README.

The following were checked verbatim against the full text and confirmed:

- MARLIN's two TurtleBot3 Waffle robots running ROS 2 Humble;
- MARLIN's single-slot and two-slot corridors;
- RoCo's 86.7% success within 5 attempts over 30 runs;
- Garg et al.'s 5–50 agents;
- GameChat's gpt-4o-mini and its priority example;
- Chandra et al.'s F1/10, Jackal and Spot platforms and their metric list.

**Checked against the abstract only.**

- *Paywalled, with no open copy found:* Mannucci et al. 2019 [@mannucci2019provably], Singh et al. 2023 [@nodetorobot2023] and Jäger & Nebel 2001 [@jager2001decentralized], marked as such in Section 5.
- *Open-access, but the PDF could not be fetched automatically (bot challenge):* Matos et al. [@commfail2021], Li et al. [@avmvbottleneck2023] and the ACM delay-tolerant intersection paper [@delaytolerant2019].
- *Checked against the arXiv text, because the publisher copy was not reachable:* Chandra et al. [@chandra2025deadlock; @chandra2026social] (Springer), [@grover2023before] and [@okumura2022pibt].
- Works outside the comparison table and outside any quantitative claim are summarised from their abstracts.

**Effect on conclusions.** The top-5 works and the three research gaps are unchanged.

<!-- end-cited -->

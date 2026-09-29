<!-- Cover letter draft for the Journal of Classification submission.
     Everything in [[double brackets]] is a placeholder: the headline findings
     must be filled in AFTER the re-analysis, from the final tables, not from v4.
     Target length: one page. -->

[[Date]]

To: [[Name of the Editor / Editor-in-Chief]], Editor, *Journal of Classification*

Dear [[Editor's name]],

We submit our manuscript **"Downstream Utility of Synthetic Data for Clustering"** for consideration as an article in the *Journal of Classification*.

**What the paper does.** Synthetic data are increasingly released in place of confidential records. Most ways of judging their quality compare distributions, or look at supervised prediction tasks. Much less is known about whether a *cluster analysis* run on a synthetic release gives the same answers as the same analysis run on the original data. This question is specific to classification: the output of a clustering method depends on the geometry of the point cloud, and a synthesiser can change that geometry while keeping marginal and pairwise summaries largely intact. We study the question for sequential CART synthesis (the default engine of the R package *synthpop*). We use a factorial simulation of 144 scenarios that crosses group separation, number of groups, dimensionality, correlation and component distribution (Normal and Gamma). Each original dataset is synthesised repeatedly, and we compare *k*-means with Ward's hierarchical linkage. Utility is measured in two ways, against the planted structure and against the analysis of the original data. This separates the effect of synthesis from the difficulty of the clustering problem itself. The partition-level measures (estimated number of groups, centroid displacement, dispersion and group-balance distortion) are computed after Hungarian alignment of the clusters.

**Main findings** (to be completed after the re-analysis):

- [[Finding 1: agreement between the numbers of clusters estimated from synthetic and from original data, and how it depends on separation and on the number of groups. Give the final estimates with their uncertainty.]]
- [[Finding 2: comparison of k-means and Ward's linkage against the planted truth versus against the original-data analysis.]]
- [[Finding 3: effect of the component distribution (Normal vs Gamma) and of dimensionality on geometric distortion.]]

**Scope of the claims.** The conclusions hold for one synthesiser (CART with the settings stated in the paper), two clustering algorithms, simulated Gaussian and Gamma mixtures with N = 1000, and the silhouette rule for choosing the number of clusters. We do not claim that they generalise to other synthesisers, to other clustering methods or to real data. The paper frames utility as a property of the combination of data, generator and analysis, to be checked for each intended use. The full pipeline is released so that readers can extend the design.

**Fit with the journal.** The paper deals with the recovery and stability of cluster structure, the choice of the number of clusters and partition comparison. These topics are central to the *Journal of Classification*, and the paper builds on work published in it (e.g. Hubert and Arabie, 1985; Aschenbruck et al., 2023). [[Optional: one sentence on the intended readership, e.g. statistical agencies evaluating synthetic releases.]]

**Declarations.** The manuscript is original. It has not been published and is not under consideration elsewhere. All five authors have approved the submission. The study extends a bachelor's thesis by one of the authors (Universitat Politècnica de Catalunya, 2025), which is cited in the manuscript; the thesis is not a peer-reviewed publication. [[Confirm, and mention any preprint or conference presentation.]] Because the journal uses double-anonymous review, the manuscript has been anonymised. Author details, funding, competing interests and author contributions are on the separate title page. During review the code is available through an anonymised repository link. [[Competing interests: none / specify.]] [[Optional: suggested or opposed reviewers, if the submission system asks for them.]]

Thank you for considering our manuscript.

Yours sincerely,

[[Corresponding author's name]], on behalf of all authors
[[Affiliation, e-mail, postal address, telephone]]

Oriol Farrés Vilar (Department of Computer Science, Universitat Politècnica de Catalunya)
Jordi Cortés (Department of Statistics and Operations Research, Universitat Politècnica de Catalunya)
Xinnuo Chen (Department of Statistical Science, University College London)
Victoria López (CUNEF Universidad, Madrid)
Daniel Fernández (Department of Statistics and Operations Research, Universitat Politècnica de Catalunya)

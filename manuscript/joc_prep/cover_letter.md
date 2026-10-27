<!-- Cover letter for the Journal of Classification submission (v5).
     The findings are the final v5 values, checked in VERIFICATION.md;
     case study, n = 50 replication and affiliations updated 27 Oct 2026.
     Remaining placeholders are in [[double brackets]]; they are administrative
     and must be completed by the corresponding author.
     PDF: python joc_prep/make_cover_letter.py (from manuscript/). -->

[[Date]]

To: [[Name of the Editor / Editor-in-Chief]], Editor, *Journal of Classification*

Dear [[Editor's name]],

We submit our manuscript **"Cluster Analysis of CART-Synthesised Data: A Factorial Simulation of k-Means and Ward's Linkage"** for consideration as an article in the *Journal of Classification*.

**What the paper does.** Synthetic data are increasingly released in place of confidential records, but little is known about whether a *cluster analysis* of a synthetic release gives the same answers as the same analysis of the original data. We study this for sequential CART synthesis, the default engine of the R package *synthpop*, in a factorial simulation of 144 scenarios crossing group separation, number of groups, dimensionality, correlation and component distribution (Normal and Gamma), with 720,000 synthetic-versus-original evaluations. We compare *k*-means with Ward's linkage, measure agreement against both the planted structure and the analysis of the original data, and read every result against a bootstrap null: the same analysis applied to bootstrap resamples of the original data, which is the synthesis procedure without the tree step.

**Main findings.**

- Agreement between the numbers of groups estimated from synthetic and original data is governed by separation (for *k*-means from 0.684 when groups overlap to 0.982 when they are well separated) and depends little on the number of groups. Most of what the planted-truth comparison records as a failure of synthesis is a failure of clustering under overlap. Beyond resampling, CART lowers agreement by 0.032 (*k*-means) and 0.016 (Ward), a small but consistent loss.
- For a researcher who clusters a synthetic release, *k*-means reproduces the original number of groups more often than Ward (0.839 versus 0.811; Wilcoxon *p* = 5.4 × 10⁻⁵ over the 144 scenarios). This happens on skewed Gamma data (0.809 versus 0.731), not on Normal data (0.869 versus 0.890). The bootstrap null shows that the advantage reflects the greater stability of the *k*-means estimate of *k* under resampling (bootstrap agreement 0.871 versus 0.826), not smaller damage from CART. Against the planted truth the two methods do not differ (0.575 versus 0.579).
- Resampling alone reproduces most of the centroid, dispersion and group-balance distortion. CART adds a positive excess in almost every scenario, and this excess is not smaller for *k*-means. In relative terms CART changes within-cluster dispersion by about 2.7 percentage points beyond resampling, and this excess grows rather than shrinks with separation. The silhouette profile is almost unchanged by synthesis, so it would not flag these distortions.
- A case study on the Reaven–Miller diabetes data (145 patients) shows the same pattern. Agreement on the number of groups stays close to its resampling reference for both methods (0.629 and 0.632, against 0.667 and 0.637 under resampling), while CART adds distortion to every geometric metric and moves patients between groups: the adjusted Rand index between the original partition and the partition transferred from the synthetic data is 0.856 (*k*-means) and 0.797 (Ward), against 0.922 and 0.837 under resampling.

**Scope of the claims.** The conclusions hold for one synthesiser (CART with the settings stated in the paper), two clustering algorithms, simulated Normal and Gamma mixtures with equal group sizes and N = 1000, and the silhouette rule for choosing the number of clusters. A replication with ten times as many original datasets per scenario (7,200) leaves every conclusion unchanged and makes the larger loss of *k*-means beyond resampling clear (Wilcoxon *p* = 1.2 × 10⁻⁵, against 0.040 in the main design). We do not claim that the results generalise to other synthesisers, to other clustering methods or, beyond the single case study, to real data. The paper frames utility as a property of the combination of data, generator and analysis, to be checked against a resampling reference for each intended use.

**Fit with the journal.** The paper deals with the recovery and stability of cluster structure and the choice of the number of clusters, topics central to the *Journal of Classification*, and it builds on work published in it (e.g. Hubert and Arabie, 1985; Aschenbruck et al., 2023). It should interest statistical agencies and data holders who evaluate synthetic releases, and analysts who intend to cluster them.

**Declarations.** The manuscript is original. It has not been published and is not under consideration elsewhere. All five authors have approved the submission. The study extends a bachelor's thesis by one of the authors (Universitat Politècnica de Catalunya, 2025), which is cited in the manuscript (in anonymised form in the version for review); the thesis is not a peer-reviewed publication. [[Confirm, and mention any preprint or conference presentation.]] Because the journal uses double-anonymous review, the manuscript and the supplementary material have been anonymised. Author details, funding, competing interests and author contributions are on the separate title page. During review the code is available through an anonymised repository link. The authors have no competing interests to declare. [[Optional: suggested or opposed reviewers, if the submission system asks for them.]]

Thank you for considering our manuscript.

Yours sincerely,

[[Corresponding author's name]], on behalf of all authors
[[Affiliation, e-mail, postal address, telephone]]

Oriol Farrés Vilar (Department of Computer Science, Universitat Politècnica de Catalunya)
Jordi Cortés (Department of Statistics and Operations Research, and Institute for Research and Innovation in Health (IRIS), Universitat Politècnica de Catalunya)
Xinnuo Chen (Department of Statistical Science, University College London)
Victoria López (CUNEF Universidad, Madrid)
Daniel Fernández (Institute for Research and Innovation in Health (IRIS), Universitat Politècnica de Catalunya)

# Introduction references — for vetting

22 records, all retrieved from OpenAlex and screened on their abstracts. 21 are cited
in the draft; the one exception is flagged in its row. Cut anything you or Dani
disagree with — the draft still compiles, it just cites less.

The four marked **[stats]** were added in a second pass aimed specifically at
official-statistics and methodological sources, since the first pass came back
almost entirely biomedical. The classics you already had (Rubin 1993, Little 1993,
Drechsler 2011, Snoke 2018) remain in the bibliography.


## Block 1 — what synthetic data is, and where it is used

| Cited | Reference | Venue | Cites | Why it fits |
|---|---|---|---|---|
| no | Zhu et al. (2019) *Electrocardiogram generation with a bidirectional LSTM-CNN generative adversarial network* <br>`10.1038/s41598-019-42516-z` | Scientific Reports | 543 | In `refs.bib` but **not cited**: GAN-generated ECG waveforms, too far from tabular CART synthesis. Delete if you agree. |
| yes | Nowok et al. (2016) *synthpop: Bespoke Creation of Synthetic Data in R* <br>`10.18637/jss.v074.i11` | Journal of Statistical Software | 388 | Defines synthetic data as mimicking original data while preserving variable relationships without disclosive records. |
| yes | Giuffrè et al. (2023) *Harnessing the power of synthetic data in healthcare: innovation, application, and privacy* <br>`10.1038/s41746-023-00927-3` | npj Digital Medicine | 356 | Defines synthetic data and surveys applications across finance, healthcare, and policy contexts. |
| yes | Gonzales et al. (2023) *Synthetic data in health care: A narrative review* <br>`10.1371/journal.pdig.0000082` | PLOS Digital Health | 283 | Defines synthetic data as innovation enabling broader data sharing; surveys applications in health care context. |
| yes | Goyal et al. (2024) *A Systematic Review of Synthetic Data Generation Techniques Using Generative AI* <br>`10.3390/electronics13173509` | Electronics | 203 | Defines synthetic data, origins in privacy/data scarcity, surveys generation techniques (LLMs, GANs, VAEs). |
| yes | Quintana et al. (2020) *A synthetic dataset primer for the biobehavioural sciences to promote reproducibility and hypothesis generation* <br>`10.7554/elife.53275` | eLife | 134 | Defines synthetic data, origins in statistical disclosure control (census), and preserves statistical properties and relationships. |
| yes | Matthews et al. (2011) **[stats]** *Data confidentiality: A review of methods for statistical disclosure limitation and methods for assessing privacy* <br>`10.1214/11-ss074` | Statistics Surveys | 90 | Reviews statistical disclosure control methods and privacy assessment techniques—foundational for understanding synthetic data origins in disclosure limitation. |
| yes | Templ et al. (2017) **[stats]** *Simulation of Synthetic Complex Data: The R Package simPop* <br>`10.18637/jss.v079.i10` | Journal of Statistical Software | 78 | Defines synthetic data origin in disclosure control, categorizes generation approaches (reconstruction, optimization, model-based), addresses quality/similarity. |
| yes | Kokosi et al. (2022) **[stats]** *An overview on synthetic administrative data for research* <br>`10.23889/ijpds.v7i1.1727` | International Journal for Population Data Science | 23 | Defines synthetic data, its origin in disclosure control, and use cases in administrative research with data access facilitation. |

## Block 2 — clustering applications and algorithms

| Cited | Reference | Venue | Cites | Why it fits |
|---|---|---|---|---|
| yes | Ahmed et al. (2020) *The k-means Algorithm: A Comprehensive Survey and Performance Evaluation* <br>`10.3390/electronics9081295` | Electronics | 1650 | Describes k-means as powerful and popular algorithm; surveys limitations and performance of a key clustering method. |
| yes | Zappia et al. (2018) *Clustering trees: a visualization for evaluating clusterings at multiple resolutions* <br>`10.1093/gigascience/giy083` | GigaScience | 1186 | Describes clustering applications (single-cell RNA-seq cell typing) and reviews algorithm variation issues. |
| yes | Liu et al. (2019) *A comparison framework and guideline of clustering methods for mass cytometry data* <br>`10.1186/s13059-019-1917-7` | Genome biology | 191 | Compares nine clustering methods (unsupervised and semi-supervised) for mass cytometry, demonstrating recent algorithmic applications in a specialized domain. |

## Block 3 — why synthetic data is needed (privacy, augmentation)

| Cited | Reference | Venue | Cites | Why it fits |
|---|---|---|---|---|
| yes | Gonçalves et al. (2020) *Generation and evaluation of synthetic patient data* <br>`10.1186/s12874-020-00977-1` | BMC Medical Research Methodology | 384 | Motivates synthetic data for privacy protection in ML; addresses lack of available patient data due to privacy concerns. |
| yes | Rankin et al. (2020) *Reliability of Supervised Machine Learning Using Synthetic Data in Health Care: Model to Preserve Privacy for Data Sharing* <br>`10.2196/18910` | JMIR Medical Informatics | 168 | Motivates synthetic data for privacy protection in sensitive health datasets; evaluates utility for downstream ML. |
| yes | Bhanot et al. (2021) *The Problem of Fairness in Synthetic Healthcare Data* <br>`10.3390/e23091165` | Entropy | 98 | Motivates synthetic data for privacy protection in healthcare; addresses need to enable research with restricted data. |
| yes | Emam et al. (2020) *Evaluating Identity Disclosure Risk in Fully Synthetic Health Data: Model Development and Validation* <br>`10.2196/23139` | Journal of Medical Internet Research | 86 | Motivates synthetic data for privacy protection; addresses identity disclosure risk in fully synthetic data sharing. |

## Block 4 — the utility concept

| Cited | Reference | Venue | Cites | Why it fits |
|---|---|---|---|---|
| yes | Reiner‐Benaim et al. (2019) *Analyzing Medical Research Results Based on Synthetic Data and Their Relation to Real Data Results: Systematic Comparison From Five Observational Studies* <br>`10.2196/16492` | JMIR Medical Informatics | 145 | Validates synthetic data results against real data; directly addresses utility/analytical validity relationship. |
| yes | Zhao et al. (2024) *CTAB-GAN+: enhancing tabular data synthesis* <br>`10.3389/fdata.2023.1296508` | Frontiers in Big Data | 106 | Explicitly addresses utility-privacy tradeoff: 'Striking the best trade-off remains yet a challenging research question.' |
| yes | Yan et al. (2022) *A Multifaceted benchmarking of synthetic electronic health record generation models* <br>`10.1038/s41467-022-35295-1` | Nature Communications | 90 | Introduces systematic benchmarking framework to appraise utility and privacy metrics for synthetic data. |
| yes | Emam et al. (2022) *Utility Metrics for Evaluating Synthetic Health Data Generation Methods: Validation Study* <br>`10.2196/35734` | JMIR Medical Informatics | 72 | Evaluates and validates utility metrics for comparing synthetic data generation methods on analytical workloads. |
| yes | Lautrup et al. (2024) **[stats]** *Systematic Review of Generative Modelling Tools and Utility Metrics for Fully Synthetic Tabular Data* <br>`10.1145/3704437` | ACM Computing Surveys | 17 | Examines synthetic data generation methods and utility measurement; addresses lack of agreement on evaluation metrics. |
| yes | Snoke et al. (2018) *General and Specific Utility Measures for Synthetic Data* <br>`10.1111/rssa.12358` | Journal of the Royal Statistical Society Series A (Statistics in Society) | 13 | Defines general vs specific utility of synthetic data and derives utility measure (pMSE) for synthetic data evaluation. |
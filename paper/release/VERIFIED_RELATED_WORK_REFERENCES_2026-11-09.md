# Verified related-work references for scoped knowledge-poisoning paper

**Status:** Bibliographic metadata and public source links reviewed on 9 November 2026; manuscript author must verify final citation style and exact claims before submission. These sources inform **background**, not factual adjudication of any 2Wiki poisoned case.

| ID | Authors, year, title and publication | Verified public locator | Relation to this manuscript |
|---|---|---|---|
| R1 | Wei Zou, Runpeng Geng, Binghui Wang, and Jinyuan Jia (2025). *PoisonedRAG: Knowledge Corruption Attacks to Retrieval-Augmented Generation of Large Language Models.* 34th USENIX Security Symposium, pp. 3827–3844. | https://www.usenix.org/conference/usenixsecurity25/presentation/zou-poisonedrag | Knowledge-base attack and chosen-target answer motivation; this study examines transfer/cost under its own controlled frozen protocol rather than reproducing the published attack |
| R2 | Jiaqi Xue, Mengxin Zheng, Yebowen Hu, Fei Liu, Xun Chen, and Qian Lou (2024). *BadRAG: Identifying Vulnerabilities in Retrieval Augmented Generation of Large Language Models.* arXiv:2406.00083 (preprint). | https://arxiv.org/abs/2406.00083 | Retrieval-stage poisoning and downstream generation vulnerability; preprint status disclosed rather than inventing a conference |
| R3 | Zhiyuan Chang, Mingyang Li, Xiaojun Jia, Junjie Wang, Yuekai Huang, Ziyou Jiang, Yang Liu, and Qing Wang (2025). *One Shot Dominance: Knowledge Poisoning Attack on Retrieval-Augmented Generation Systems.* Findings of EMNLP 2025. | https://aclanthology.org/2025.findings-emnlp.1023/ | Illustrates that attack design may vary in injected-document count and multi-hop complexity; not an unseen-family experiment performed by this repo |
| R4 | Soyeong Jeong, Jinheon Baek, Sukmin Cho, Sung Ju Hwang, and Jong Park (2024). *Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity.* NAACL 2024, pp. 7036–7050. DOI 10.18653/v1/2024.naacl-long.389. | https://aclanthology.org/2024.naacl-long.389/ | Adaptive routing by query complexity, **not** equivalent to the repo's current bounded two-round coverage heuristic |
| R5 | Harsh Trivedi, Niranjan Balasubramanian, Tushar Khot, and Ashish Sabharwal (2023). *Interleaving Retrieval with Chain-of-Thought Reasoning for Knowledge-Intensive Multi-Step Questions.* ACL 2023. | https://aclanthology.org/2023.acl-long.557/ | Background on genuine retrieval/reasoning interleaving; the repo has not completed equivalent poisoned multi-round QA evaluations |
| R6 | Akari Asai, Zeqiu Wu, Yizhong Wang, Avi Sil, and Hannaneh Hajishirzi (2024). *Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection.* ICLR 2024. | https://proceedings.iclr.cc/paper_files/paper/2024/hash/25f7be9694d7b32d5cc670927b8091e1-Abstract-Conference.html | Background on retrieval-conditioned self-reflection, not a model or trained detector used in our local study |

## Suggested related-work organization

**Knowledge-base poisoning and transfer:** [R1] and [R2] establish retrieval-side attack surfaces; [R3] illustrates single-document attacks with multi-hop questions. This work's *already completed* source-crafted HotpotQA matrix addresses source-to-target transfer among four source and five target retrieval pipelines, with construction-failure accounting and repeated-query clustering.

**Adaptive/multi-round retrieval:** [R4], [R5] and [R6] motivate adaptive retrieval and evidence-conditioned reasoning. In the present repo the two-round policy exists as an implementation with synthetic tests and an optional real **clean-development retrieval-only** diagnostic; no real matched poisoned QA result for this policy has been verified.

**Novelty guard:** Do **not** claim the first knowledge corruption attack, the first adaptive retrieval design, or a proven defense. The contribution of the existing study is the *measured experimental comparison*, including negative and null results, denominator handling, source-transfer structure and local retrieval-work accounting.

**Bibliography check needed before submission:** Fetch final BibTeX from each publisher/anthology entry; review spellings and pagination in the target template. No research benchmark result from any cited external paper is represented as this repo's outcome.

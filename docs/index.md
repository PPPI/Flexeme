# FLEXEME
[![DOI](https://zenodo.org/badge/265828516.svg)](https://zenodo.org/badge/latestdoi/265828516)

Today, most developers bundle changes into commits that they sub-mit to a shared code repository. 
Tangled commits intermix distinctconcerns, such as a bug fix and a new feature. 
They cause issuesfor developers, reviewers, and researchers alike: they restrict theusability of tools such as git bisect, make patch comprehensionmore difficult, and force researchers who mine software reposi-tories to contend with noise. 
We present a novel data structure,the 𝛿-NFG, a multiversion Program Dependency Graph augmentedwith name flows. 
A 𝛿-NFG directly and simultaneously encodes dif-ferent program versions, thereby capturing commits, and annotatesdata flow edges with the names/lexemes that flow across them. 
Our technique, Flexeme, builds a 𝛿-NFG from commits, then applies Agglomerative Clustering using Graph Similarity to that 𝛿-NFG tountangle its commits. 
At the untangling task on a C# corpus, our implementation, Heddle, improves the state-of-the-art on accuracy by 0.14, achieving 0.81, in a fraction of the time: Heddle is 32 times faster than the previous state-of-the-art.

This work was done under the supervision of [Earl Barr](http://earlbarr.com/) and 
in collaboration with [Santanu Dash](http://santanu.uk/), and [Miltos Allamanis](https://miltos.allamanis.com/).

![Overview of Flexme](overview.png)


# Self-replication in Life-like cellular automata: an autonomous search

## Abstract

An autonomous agent explored 45 hypothesis nodes and evaluated 913 rules. The strongest candidate was
B36/S23 with fitness 4.0 (n31).

## Question

Find a Life-like CA rule (B../S..) and a seed of at most 5x5 cells under which the seed self-replicates: after N steps the grid contains 2 or more disjoint copies of the seed.

## Method

Each node proposes rules and a seed, simulates 60 steps on a 64x64 torus, and counts disjoint copies of the seed.

## Search summary

| node | rule | seed | copies | stable |
|------|------|------|--------|--------|
| n31 | B36/S23 | [[0, 1, 0], [0, 0, 1], [1, 1, 1]] | 4 | True |
| n2 | B28/S023 | [[1, 1], [1, 1]] | 3 | True |
| n9 | B27/S | [[0, 0, 1, 1, 1], [0, 1, 0, 0, 1], [1, 0, 0, 0, 1], [1, 0, 0, 1, 0], [1, 1, 1, 0, 0]] | 4 | True |
| n13 | B148/S37 | [[1, 1, 0], [0, 1, 1], [0, 1, 0]] | 4 | True |
| n14 | B8/S18 | [[1, 1, 0], [0, 1, 1], [0, 1, 0]] | 4 | True |

![](frames/n0_20.png)

## Findings

The HighLife family dominated the frontier (n17), and the best node refined it further (n31).

## Dead ends

Seeds-type explosive rules filled the grid and scored low (n3).

## Limitations

The copy counter is a proxy; it cannot distinguish replication from coincidental debris.

## Next experiments

Larger seeds, longer runs, and a translation-aware copy metric.

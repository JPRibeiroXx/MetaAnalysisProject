"""
Pure utility functions used by app.py — importable without Streamlit.
"""
from __future__ import annotations
import json
import re
import urllib.parse
import urllib.request
import pandas as pd


# ── MeSH term fetcher (NLM REST API) ──────────────────────────────────────────

def fetch_mesh_terms(query: str, max_results: int = 8) -> list[str]:
    """
    Query NLM's MeSH descriptor API for terms matching `query`.
    Returns PubMed-formatted strings like '"Aging"[MeSH Terms]'.
    Falls back to [] on any network/parsing error or empty query.
    """
    if not query or not query.strip():
        return []

    encoded = urllib.parse.quote(query.strip())
    url = (
        f"https://id.nlm.nih.gov/mesh/lookup/descriptor"
        f"?label={encoded}&match=contains&limit={max_results}&lang=eng&tt=JSON"
    )
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            seen: set[str] = set()
            results: list[str] = []
            for hit in data[:max_results]:
                label = hit.get("label", "")
                if label and label not in seen:
                    seen.add(label)
                    results.append(f'"{label}"[MeSH Terms]')
            return results
    except Exception:
        return []


# ── Chip term application ──────────────────────────────────────────────────────

def apply_pending_term(existing_terms: str, new_term: str) -> str:
    """
    Append `new_term` to `existing_terms` (one term per line), skipping duplicates.
    Returns the updated string with no blank lines.
    """
    lines = [l.strip() for l in existing_terms.splitlines() if l.strip()]
    if new_term not in lines:
        lines.append(new_term)
    return "\n".join(lines)


# ── Term suggestion engine ─────────────────────────────────────────────────────
# Each key is a concept keyword; the value is an ordered list of
# PubMed-formatted search terms (MeSH headings first, then tiab phrases).
# Field tag placeholder `{tag}` is replaced at call time with tiab / tw / etc.

_TERM_SUGGESTIONS: dict[str, list[str]] = {
    # ── Cardiac / cardiovascular ──────────────────────────────────────────────
    "cardiac": [
        '"Heart"[MeSH Terms]',
        '"Myocytes, Cardiac"[MeSH Terms]',
        '"Cardiovascular Diseases"[MeSH Terms]',
        'cardiac[{tag}]', 'heart[{tag}]', 'myocardial[{tag}]', 'cardiomyocyte[{tag}]',
    ],
    "heart": [
        '"Heart"[MeSH Terms]',
        '"Heart Diseases"[MeSH Terms]',
        'heart[{tag}]', 'cardiac[{tag}]', 'myocardial[{tag}]',
    ],
    "cardiomyocyte": [
        '"Myocytes, Cardiac"[MeSH Terms]',
        '"Induced Pluripotent Stem Cells"[MeSH Terms]',
        'cardiomyocyte[{tag}]', 'hiPSC-CM[{tag}]',
        '"iPSC-derived cardiomyocyte"[{tag}]',
        '"stem cell-derived cardiomyocyte"[{tag}]',
    ],
    # ── In vitro models ───────────────────────────────────────────────────────
    "model": [
        '"Tissue Engineering"[MeSH Terms]',
        '"Organ Culture Techniques"[MeSH Terms]',
        '"Lab-On-A-Chip Devices"[MeSH Terms]',
        '"engineered heart tissue"[{tag}]',
        '"heart-on-a-chip"[{tag}]',
        '"organ-on-a-chip"[{tag}]',
        '"microphysiological system"[{tag}]',
        'MPS[{tag}]', 'EHT[{tag}]',
        '"cardiac organoid"[{tag}]', '"cardiac spheroid"[{tag}]',
        '"3D cardiac"[{tag}]',
    ],
    "organoid": [
        '"Organoids"[MeSH Terms]',
        '"Spheroids, Cellular"[MeSH Terms]',
        'organoid[{tag}]', 'spheroid[{tag}]',
        '"3D culture"[{tag}]', '"self-assembled"[{tag}]',
        '"cardiac organoid"[{tag}]',
    ],
    "chip": [
        '"Lab-On-A-Chip Devices"[MeSH Terms]',
        '"Microfluidics"[MeSH Terms]',
        '"organ-on-a-chip"[{tag}]', '"heart-on-a-chip"[{tag}]',
        '"microphysiological"[{tag}]', 'microfluidic[{tag}]',
    ],
    "tissue engineering": [
        '"Tissue Engineering"[MeSH Terms]',
        '"Bioprinting"[MeSH Terms]',
        '"tissue engineering"[{tag}]', '"engineered tissue"[{tag}]',
        'bioprinting[{tag}]', 'scaffold[{tag}]', 'hydrogel[{tag}]',
    ],
    "ipsc": [
        '"Induced Pluripotent Stem Cells"[MeSH Terms]',
        '"Cell Differentiation"[MeSH Terms]',
        'iPSC[{tag}]', 'hiPSC[{tag}]',
        '"induced pluripotent"[{tag}]',
        '"pluripotent stem cell"[{tag}]',
        'reprogramming[{tag}]',
    ],
    # ── Aging / senescence ────────────────────────────────────────────────────
    "aging": [
        '"Aging"[MeSH Terms]',
        '"Cellular Senescence"[MeSH Terms]',
        '"Inflammaging"[MeSH Terms]',
        'aging[{tag}]', 'aged[{tag}]', 'ageing[{tag}]',
        '"age-related"[{tag}]', 'senescence[{tag}]',
        'inflammaging[{tag}]', 'geroscience[{tag}]',
    ],
    "senescence": [
        '"Cellular Senescence"[MeSH Terms]',
        '"Cyclin-Dependent Kinase Inhibitor p21"[MeSH Terms]',
        'senescence[{tag}]', '"cellular senescence"[{tag}]',
        '"replicative senescence"[{tag}]',
        'p21[{tag}]', 'p16[{tag}]', 'SASP[{tag}]',
    ],
    "maturation": [
        '"Cell Differentiation"[MeSH Terms]',
        '"Myocyte Development"[MeSH Terms]',
        'maturation[{tag}]', '"adult-like"[{tag}]',
        '"metabolic maturation"[{tag}]',
        '"structural maturation"[{tag}]',
        '"functional maturation"[{tag}]',
    ],
    # ── Disease / pathology ───────────────────────────────────────────────────
    "fibrosis": [
        '"Fibrosis"[MeSH Terms]',
        '"Myofibroblasts"[MeSH Terms]',
        '"Transforming Growth Factor beta"[MeSH Terms]',
        'fibrosis[{tag}]', 'fibrotic[{tag}]',
        '"extracellular matrix"[{tag}]', 'TGF-beta[{tag}]',
        '"collagen deposition"[{tag}]', 'myofibroblast[{tag}]',
    ],
    "hypertrophy": [
        '"Cardiomegaly"[MeSH Terms]',
        '"Hypertrophy, Left Ventricular"[MeSH Terms]',
        'hypertrophy[{tag}]', 'hypertrophic[{tag}]',
        '"cardiac remodeling"[{tag}]', '"cardiomegaly"[{tag}]',
    ],
    "heart failure": [
        '"Heart Failure"[MeSH Terms]',
        '"Ventricular Dysfunction"[MeSH Terms]',
        '"heart failure"[{tag}]', '"HFpEF"[{tag}]', '"HFrEF"[{tag}]',
        '"cardiac dysfunction"[{tag}]',
        '"reduced ejection fraction"[{tag}]',
    ],
    "arrhythmia": [
        '"Arrhythmias, Cardiac"[MeSH Terms]',
        '"Long QT Syndrome"[MeSH Terms]',
        '"Torsades de Pointes"[MeSH Terms]',
        'arrhythmia[{tag}]', '"QT prolongation"[{tag}]',
        'torsades[{tag}]', 'proarrhythmia[{tag}]',
        '"triggered activity"[{tag}]',
    ],
    "ischemia": [
        '"Myocardial Ischemia"[MeSH Terms]',
        '"Myocardial Infarction"[MeSH Terms]',
        '"Reperfusion Injury"[MeSH Terms]',
        'ischemia[{tag}]', '"myocardial infarction"[{tag}]',
        'reperfusion[{tag}]', 'hypoxia[{tag}]',
    ],
    # ── Electrophysiology / function ──────────────────────────────────────────
    "electrophysiology": [
        '"Electrophysiology"[MeSH Terms]',
        '"Action Potentials"[MeSH Terms]',
        '"Patch-Clamp Techniques"[MeSH Terms]',
        '"Microelectrode Arrays"[MeSH Terms]',
        'electrophysiology[{tag}]', '"action potential"[{tag}]',
        'APD[{tag}]', '"field potential duration"[{tag}]',
        'FPD[{tag}]', 'MEA[{tag}]',
        '"multi-electrode array"[{tag}]',
    ],
    "calcium": [
        '"Calcium Signaling"[MeSH Terms]',
        '"Ryanodine Receptor Calcium Release Channel"[MeSH Terms]',
        '"Sarcoplasmic Reticulum Calcium-Transporting ATPases"[MeSH Terms]',
        '"calcium transient"[{tag}]', '"calcium handling"[{tag}]',
        '"calcium imaging"[{tag}]',
        'SERCA[{tag}]', 'ryanodine[{tag}]', 'Ca2+[{tag}]',
    ],
    "contractility": [
        '"Myocardial Contraction"[MeSH Terms]',
        '"Cardiac Output"[MeSH Terms]',
        'contractility[{tag}]', '"twitch force"[{tag}]',
        '"sarcomere shortening"[{tag}]',
        'force[{tag}]', 'actomyosin[{tag}]',
    ],
    "metabolism": [
        '"Energy Metabolism"[MeSH Terms]',
        '"Mitochondria, Heart"[MeSH Terms]',
        '"Fatty Acids"[MeSH Terms]',
        'metabolism[{tag}]', 'metabolic[{tag}]',
        '"fatty acid oxidation"[{tag}]',
        'mitochondria[{tag}]', 'ATP[{tag}]',
        '"oxidative phosphorylation"[{tag}]',
    ],
    # ── Engineering interventions ─────────────────────────────────────────────
    "electrical stimulation": [
        '"Electric Stimulation"[MeSH Terms]',
        '"Cardiac Pacing, Artificial"[MeSH Terms]',
        '"electrical stimulation"[{tag}]', 'pacing[{tag}]',
        '"electrical field stimulation"[{tag}]',
        'electrostimulation[{tag}]',
    ],
    "mechanical": [
        '"Mechanotransduction, Cellular"[MeSH Terms]',
        '"Stress, Mechanical"[MeSH Terms]',
        '"mechanical loading"[{tag}]', 'stretch[{tag}]',
        '"cyclic stretch"[{tag}]',
        'preload[{tag}]', 'afterload[{tag}]',
    ],
    "stiffness": [
        '"Extracellular Matrix"[MeSH Terms]',
        '"Elastic Modulus"[MeSH Terms]',
        '"substrate stiffness"[{tag}]', '"matrix stiffness"[{tag}]',
        '"Young\'s modulus"[{tag}]', 'viscoelastic[{tag}]',
        'stiffness[{tag}]',
    ],
    "co-culture": [
        '"Coculture Techniques"[MeSH Terms]',
        '"Fibroblasts"[MeSH Terms]',
        '"Endothelial Cells"[MeSH Terms]',
        '"co-culture"[{tag}]', 'coculture[{tag}]',
        '"multicellular"[{tag}]', 'fibroblast[{tag}]',
        'endothelial[{tag}]', '"stromal cell"[{tag}]',
    ],
    # ── Drug / pharmacology / toxicity ────────────────────────────────────────
    "drug": [
        '"Pharmaceutical Preparations"[MeSH Terms]',
        '"Cardiotonic Agents"[MeSH Terms]',
        '"Small Molecule Libraries"[MeSH Terms]',
        'drug[{tag}]', 'compound[{tag}]',
        '"small molecule"[{tag}]', 'pharmacological[{tag}]',
    ],
    "toxicity": [
        '"Cardiotoxicity"[MeSH Terms]',
        '"Drug-Related Side Effects and Adverse Reactions"[MeSH Terms]',
        '"hERG Channels"[MeSH Terms]',
        'cardiotoxicity[{tag}]', '"drug-induced cardiotoxicity"[{tag}]',
        '"adverse effect"[{tag}]',
        '"safety pharmacology"[{tag}]', 'hERG[{tag}]',
    ],
    "screening": [
        '"High-Throughput Screening Assays"[MeSH Terms]',
        '"Drug Evaluation, Preclinical"[MeSH Terms]',
        '"drug screening"[{tag}]', '"high-throughput"[{tag}]',
        '"phenotypic screen"[{tag}]',
        '"compound library"[{tag}]',
    ],
    "prediction": [
        '"Translational Research, Biomedical"[MeSH Terms]',
        '"Models, Cardiovascular"[MeSH Terms]',
        'predict[{tag}]', 'predictive[{tag}]',
        'translational[{tag}]', '"clinical relevance"[{tag}]',
        '"in vivo correlation"[{tag}]',
    ],
    # ── Cancer ────────────────────────────────────────────────────────────────
    "cancer": [
        '"Neoplasms"[MeSH Terms]',
        '"Oncology Service, Hospital"[MeSH Terms]',
        'cancer[{tag}]', 'tumor[{tag}]', 'tumour[{tag}]',
        'malignant[{tag}]', 'oncology[{tag}]', 'neoplasm[{tag}]',
    ],
    "chemotherapy": [
        '"Antineoplastic Agents"[MeSH Terms]',
        '"Doxorubicin"[MeSH Terms]',
        '"Immune Checkpoint Inhibitors"[MeSH Terms]',
        'chemotherapy[{tag}]', 'doxorubicin[{tag}]',
        'anthracycline[{tag}]', '"checkpoint inhibitor"[{tag}]',
        '"oncology cardiotoxicity"[{tag}]',
    ],
    # ── Neuroscience ──────────────────────────────────────────────────────────
    "neuron": [
        '"Neurons"[MeSH Terms]',
        '"Synapses"[MeSH Terms]',
        '"Neurosciences"[MeSH Terms]',
        'neuron[{tag}]', 'neuronal[{tag}]', 'neural[{tag}]',
        'axon[{tag}]', 'synapse[{tag}]', 'neuropathy[{tag}]',
    ],
    "neurodegeneration": [
        '"Neurodegenerative Diseases"[MeSH Terms]',
        '"Alzheimer Disease"[MeSH Terms]',
        '"Parkinson Disease"[MeSH Terms]',
        'neurodegeneration[{tag}]', '"Alzheimer"[{tag}]',
        '"Parkinson"[{tag}]', 'amyloid[{tag}]',
        'tau[{tag}]', 'neuroinflammation[{tag}]',
    ],
    # ── Respiratory ───────────────────────────────────────────────────────────
    "lung": [
        '"Lung"[MeSH Terms]',
        '"Lung Diseases"[MeSH Terms]',
        '"Pulmonary Disease, Chronic Obstructive"[MeSH Terms]',
        'lung[{tag}]', 'pulmonary[{tag}]', 'alveolar[{tag}]',
        'respiratory[{tag}]', 'airway[{tag}]',
        'COPD[{tag}]', 'asthma[{tag}]',
    ],
    # ── Liver ─────────────────────────────────────────────────────────────────
    "liver": [
        '"Liver"[MeSH Terms]',
        '"Non-alcoholic Fatty Liver Disease"[MeSH Terms]',
        '"Chemical and Drug Induced Liver Injury"[MeSH Terms]',
        'liver[{tag}]', 'hepatic[{tag}]', 'hepatocyte[{tag}]',
        'NAFLD[{tag}]', 'NASH[{tag}]',
        'hepatotoxicity[{tag}]', 'steatosis[{tag}]',
    ],
    # ── Kidney ────────────────────────────────────────────────────────────────
    "kidney": [
        '"Kidney"[MeSH Terms]',
        '"Renal Insufficiency"[MeSH Terms]',
        '"Glomerulonephritis"[MeSH Terms]',
        'kidney[{tag}]', 'renal[{tag}]', 'nephron[{tag}]',
        'podocyte[{tag}]', 'glomerular[{tag}]',
        'nephrotoxicity[{tag}]',
    ],
    # ── Inflammation / immune ─────────────────────────────────────────────────
    "inflammation": [
        '"Inflammation"[MeSH Terms]',
        '"Cytokines"[MeSH Terms]',
        '"NF-kappa B"[MeSH Terms]',
        'inflammation[{tag}]', 'inflammatory[{tag}]',
        'cytokine[{tag}]', 'interleukin[{tag}]',
        'TNF[{tag}]', '"NF-kB"[{tag}]',
    ],
    "immune": [
        '"Immune System"[MeSH Terms]',
        '"T-Lymphocytes"[MeSH Terms]',
        '"Macrophages"[MeSH Terms]',
        'immune[{tag}]', '"T cell"[{tag}]',
        '"B cell"[{tag}]', 'macrophage[{tag}]',
        '"innate immunity"[{tag}]', '"adaptive immunity"[{tag}]',
    ],
    # ── Omics / biomarkers ────────────────────────────────────────────────────
    "transcriptomics": [
        '"Transcriptome"[MeSH Terms]',
        '"RNA-Seq"[MeSH Terms]',
        '"Single-Cell Analysis"[MeSH Terms]',
        'transcriptomics[{tag}]', '"RNA-seq"[{tag}]',
        '"gene expression"[{tag}]', '"single-cell"[{tag}]',
        'scRNA-seq[{tag}]',
    ],
    "proteomics": [
        '"Proteomics"[MeSH Terms]',
        '"Mass Spectrometry"[MeSH Terms]',
        'proteomics[{tag}]', '"protein expression"[{tag}]',
        '"mass spectrometry"[{tag}]',
        'phosphoproteomics[{tag}]',
    ],
    "genomics": [
        '"Genomics"[MeSH Terms]',
        '"Genome-Wide Association Study"[MeSH Terms]',
        '"Genetic Variation"[MeSH Terms]',
        'genomics[{tag}]', 'genome[{tag}]',
        'mutation[{tag}]', 'variant[{tag}]',
        'GWAS[{tag}]', 'SNP[{tag}]',
    ],
    "biomarker": [
        '"Biomarkers"[MeSH Terms]',
        '"Biomarkers, Tumor"[MeSH Terms]',
        'biomarker[{tag}]', '"prognostic marker"[{tag}]',
        '"diagnostic marker"[{tag}]', '"circulating biomarker"[{tag}]',
    ],
    # ── Clinical ──────────────────────────────────────────────────────────────
    "clinical": [
        '"Clinical Trials as Topic"[MeSH Terms]',
        '"Randomized Controlled Trials as Topic"[MeSH Terms]',
        '"Patients"[MeSH Terms]',
        'clinical[{tag}]', 'patient[{tag}]',
        'cohort[{tag}]', '"randomized"[{tag}]',
        'trial[{tag}]', 'outcome[{tag}]',
    ],
    "translation": [
        '"Translational Research, Biomedical"[MeSH Terms]',
        '"Models, Animal"[MeSH Terms]',
        'translational[{tag}]', '"clinical translation"[{tag}]',
        '"bench to bedside"[{tag}]', 'preclinical[{tag}]',
    ],
}


def get_term_suggestions(block_name: str, scope: str = "tiab") -> list[str]:
    """
    Return a list of suggested PubMed-formatted search terms for a given block name.
    `scope` sets the field tag: 'tiab' (title/abstract) or 'tw' (text word).
    MeSH terms are always returned as [MeSH Terms] regardless of scope.
    """
    name_words = set(re.split(r"[\s/\-,]+", block_name.lower()))
    name_words.discard("")

    results: list[str] = []
    seen: set[str] = set()

    # Score each concept key by word overlap with block name
    scored: list[tuple[int, str, list[str]]] = []
    for concept_key, terms in _TERM_SUGGESTIONS.items():
        key_words = set(re.split(r"[\s/\-,]+", concept_key.lower()))
        score = len(name_words & key_words)
        if score > 0:
            scored.append((score, concept_key, terms))

    # Sort by score descending, take top 3 matching concept groups
    scored.sort(key=lambda x: -x[0])
    for _, _, terms in scored[:3]:
        for t in terms:
            formatted = t.replace("{tag}", scope)
            if formatted not in seen:
                seen.add(formatted)
                results.append(formatted)

    return results


# ── Pattern suggestion ─────────────────────────────────────────────────────────

_PATTERN_LOOKUP: dict[str, str] = {
    # Cardiac / cardiovascular
    "cardiac":              "cardiac|heart|myocardial|cardiomyocyte|cardiovascular",
    "heart":                "heart|cardiac|myocardial|cardiovascular",
    "cardiomyocyte":        "cardiomyocyte|hiPSC-CM|iPSC-derived cardiomyocyte|stem cell-derived cardiac",
    # Tissue / organ models
    "model":                "engineered heart tissue|EHT|heart-on-a-chip|organ-on-a-chip|microphysiological|MPS|organoid|spheroid|3D cardiac",
    "organoid":             "organoid|spheroid|3D culture|self-assembled",
    "chip":                 "organ-on-a-chip|heart-on-a-chip|microphysiological|microfluidic",
    "tissue engineering":   "tissue engineering|engineered tissue|3D scaffold|bioprinting|hydrogel",
    "in vitro":             "in vitro|cell culture|2D culture|monolayer|hiPSC|iPSC",
    # Aging / senescence
    "aging":                "aging|aged|ageing|senescence|inflammaging|age-related|geroscience",
    "senescence":           "senescence|p21|p16|SASP|cellular senescence|replicative senescence",
    "maturation":           "maturation|adult-like|mature|differentiation|metabolic maturation",
    # Disease / pathology
    "fibrosis":             "fibrosis|fibrotic|collagen deposition|scarring|TGF-beta|myofibroblast",
    "hypertrophy":          "hypertrophy|hypertrophic|cardiomegaly|cardiac remodeling",
    "heart failure":        "heart failure|HF|cardiac dysfunction|reduced ejection fraction|HFpEF|HFrEF",
    "arrhythmia":           "arrhythmia|arrhythmic|QT prolongation|torsades|proarrhythmia|triggered activity",
    "ischemia":             "ischemia|ischemic|myocardial infarction|MI|reperfusion|hypoxia",
    # Electrophysiology / function
    "electrophysiology":    "electrophysiology|action potential|APD|field potential|FPD|calcium transient|patch clamp",
    "action potential":     "action potential|APD|action potential duration|voltage-sensitive dye",
    "calcium":              "calcium|Ca2+|calcium transient|calcium handling|SERCA|ryanodine",
    "contractility":        "contractility|force|twitch force|shortening|sarcomere|actomyosin",
    "metabolism":           "metabolism|metabolic|mitochondria|fatty acid oxidation|ATP|oxidative phosphorylation",
    # Engineering interventions
    "electrical stimulation": "electrical stimulation|pacing|electrical field stimulation|electrostimulation",
    "mechanical":           "mechanical loading|stretch|cyclic stretch|preload|afterload|mechanical stimulation",
    "stiffness":            "stiffness|substrate stiffness|matrix stiffness|Young's modulus|viscoelastic",
    "co-culture":           "co-culture|non-myocyte|fibroblast|endothelial|stromal|multicellular",
    # Drug / toxicity
    "drug":                 "drug|compound|small molecule|pharmacological|cardioactive|medication",
    "toxicity":             "cardiotoxicity|toxic|cytotoxic|adverse effect|safety pharmacology|hERG",
    "screening":            "drug screening|high-throughput|assay|compound library|phenotypic screen",
    "prediction":           "predict|predictive|translational|clinical relevance|in vivo correlation",
    # Cancer / oncology
    "cancer":               "cancer|tumor|tumour|malignant|oncology|neoplasm|metastasis",
    "chemotherapy":         "chemotherapy|doxorubicin|anthracycline|checkpoint inhibitor|oncology cardiotoxicity",
    # Neuroscience
    "neuron":               "neuron|neuronal|neural|axon|synapse|neuroscience|neuropathy",
    "neurodegeneration":    "neurodegeneration|Alzheimer|Parkinson|amyloid|tau|neuroinflammation",
    # Respiratory
    "lung":                 "lung|pulmonary|alveolar|respiratory|airway|COPD|asthma",
    # Liver
    "liver":                "liver|hepatic|hepatocyte|NAFLD|NASH|hepatotoxicity|steatosis",
    # Kidney
    "kidney":               "kidney|renal|nephron|podocyte|glomerular|nephrotoxicity",
    # Inflammation / immune
    "inflammation":         "inflammation|inflammatory|cytokine|interleukin|TNF|NFkB|immune",
    "immune":               "immune|immunology|T cell|B cell|macrophage|innate immunity|adaptive immunity",
    # Stem cells / iPSC
    "iPSC":                 "iPSC|hiPSC|induced pluripotent|stem cell|pluripotent|reprogramming",
    "differentiation":      "differentiation|lineage|progenitor|committed|specification",
    # Biomarker / omics
    "biomarker":            "biomarker|marker|indicator|prognostic|diagnostic|circulating",
    "transcriptomics":      "transcriptomics|RNA-seq|gene expression|single-cell|scRNA-seq|mRNA",
    "proteomics":           "proteomics|protein expression|mass spectrometry|phosphoproteomics",
    "genomics":             "genomics|genome|mutation|variant|GWAS|SNP|genetic",
    # Clinical
    "clinical":             "clinical|patient|cohort|randomized|trial|outcome|mortality|morbidity",
    "translation":          "translational|clinical translation|bench to bedside|preclinical",
}

_STOPWORDS = frozenset({
    "a", "an", "the", "of", "for", "in", "on", "to", "and", "or", "is", "are",
    "that", "this", "with", "paper", "study", "describes", "about", "involves",
    "measures", "reports", "shows", "where", "which", "it", "its", "by", "at",
    "be", "was", "were", "has", "have", "from", "as", "do", "does", "per", "into",
})


def suggest_pattern(label: str, description: str) -> str:
    """
    Return a pipe-separated regex suggestion based on label + description keywords.
    Falls back to extracting non-trivial words from the label if nothing matches.
    """
    combined = (label + " " + description).lower()

    combined_words = set(re.split(r"[\s/\-,]+", combined))

    scores: list[tuple[int, str]] = []
    for key, pattern in _PATTERN_LOOKUP.items():
        key_words = re.split(r"[\s/]+", key.lower())
        score = sum(1 for w in key_words if w and w in combined_words)
        if score:
            scores.append((score, pattern))

    if not scores:
        words = [
            w for w in re.split(r"[\s/\-,]+", combined)
            if len(w) > 2 and w not in _STOPWORDS
        ]
        seen: set[str] = set()
        deduped = [w for w in words if not (w in seen or seen.add(w))]  # type: ignore[func-returns-value]
        return "|".join(deduped[:6])

    scores.sort(key=lambda x: -x[0])
    seen_terms: set[str] = set()
    parts: list[str] = []
    for _, pattern in scores[:2]:
        for term in pattern.split("|"):
            if term not in seen_terms:
                seen_terms.add(term)
                parts.append(term)
    return "|".join(parts)


# ── Query preview builder ──────────────────────────────────────────────────────

def build_query_preview(blocks: pd.DataFrame) -> str:
    """
    Build a PubMed boolean string from a DataFrame with columns:
        Block Name | Terms | Connector
    Terms within a block are OR'd; blocks are joined by the Connector value.
    The last block's Connector is ignored (treated as terminal).
    Returns '' if no non-empty blocks exist.
    """
    parts: list[str] = []
    connectors: list[str] = []

    for _, row in blocks.iterrows():
        raw = str(row.get("Terms", "") or "")
        terms = [t.strip() for t in raw.splitlines() if t.strip()]
        if not terms:
            continue
        block_str = "(" + " OR ".join(terms) + ")"
        parts.append(block_str)
        conn = str(row.get("Connector", "AND")).strip()
        connectors.append(conn if conn not in ("—", "", "None") else None)

    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]

    result = parts[0]
    for i, part in enumerate(parts[1:]):
        conn = connectors[i] or "AND"
        result = f"({result} {conn} {part})"
    return result

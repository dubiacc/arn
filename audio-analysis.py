import json
import re
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
import numpy as np

# --- MAIN CONFIGURATION ---
# Set independent error thresholds for each testament.
ERROR_THRESHOLD_NT = 0.10
ERROR_THRESHOLD_OT = 0.15 # OT often has more names/numbers, so a higher threshold might be needed.

# --- Plotting Configuration ---
OUTPUT_DIR = Path("audio-check")
MAX_FLAGGED_CHUNKS_TO_PLOT = 250
MAX_CHAPTERS_TO_PLOT = 75

# --- Filtering Configuration ---
# Define book lists to partition the data.
NEW_TESTAMENT_BOOKS = {
    "Mt", "Mk", "Lk", "Joh", "Apg", "Roem", "1Kor", "2Kor", "Gal", "Eph",
    "Phil", "Kol", "1Thess", "2Thess", "1Tim", "2Tim", "Tit", "Phlm",
    "Hebr", "Jak", "1Petr", "2Petr", "1Joh", "2Joh", "3Joh", "Jud", "Offb"
}
OLD_TESTAMENT_BOOKS = {
    "Gen", "Ex", "Lev", "Num", "Dtn", "Jos", "Ri", "Rut", "1Sam", "2Sam",
    "1Koen", "2Koen", "1Chr", "2Chr", "Esra", "Neh", "Tob", "Jdt", "Est",
    "1Makk", "2Makk", "Ijob", "Ps", "Spr", "Koh", "Hld", "Weish", "Sir",
    "Jes", "Jer", "Klgl", "Bar", "Ez", "Dan", "Hos", "Joel", "Am", "Obd",
    "Jona", "Mi", "Nah", "Hab", "Zef", "Hag", "Sach", "Mal"
}


def normalize_text(text: str) -> str:
    """Normalizes text for comparison."""
    text = re.sub(r'[^a-z0-9\s]', '', text.lower())
    return re.sub(r'\s+', ' ', text).strip()

def print_threshold_analysis(results: list, item_type: str, value_key: str, testament_name: str):
    """Prints a statistical analysis of how many items would be flagged at different percentile thresholds."""
    if not results: return
    print(f"\n--- Statistical Threshold Impact for {item_type.title()} ({testament_name}) ---")
    total_items = len(results)
    error_rates = [r[value_key] for r in results]
    percentiles = [75, 80, 85, 90, 95, 99]
    for p in percentiles:
        threshold = np.quantile(error_rates, p / 100.0)
        flagged_count = sum(1 for rate in error_rates if rate > threshold)
        print(f"A statistical threshold of > {threshold:.3f} ({p}th percentile) would flag {flagged_count} of {total_items} {item_type}.")

def analyze_individual_chunks(all_chunk_data: list, testament_name: str, file_paths: dict):
    """PART 1: Analyzes all chunks and creates a statistical distribution plot and report."""
    print(f"\n--- Part 1: Analyzing Individual Chunks ({testament_name}) ---")
    analysis_results = []
    for entry in all_chunk_data:
        distance = entry.get("levenshtein_distance", 0)
        original_text = entry.get("original_text", "")
        text_length = len(normalize_text(original_text))
        raw_error_rate = distance / text_length if text_length > 0 else 1.0
        error_rate = min(1.0, raw_error_rate)
        analysis_results.append({"chunk_id": f"{entry.get('chapter')}/{entry.get('chunk')}", "normalized_error_rate": error_rate})

    if not analysis_results: return None
    print(f"Analyzed {len(analysis_results)} individual chunks.")
    _generate_distribution_plot([r['normalized_error_rate'] for r in analysis_results], testament_name, file_paths['distribution_plot'])

    report = {"summary_statistics": {"total_chunks": len(analysis_results)}, "all_chunks": analysis_results}
    file_paths['distribution_json'].write_text(json.dumps(report, indent=4), encoding='utf-8')
    print(f"Statistical JSON report saved to: '{file_paths['distribution_json']}'")
    print_threshold_analysis(analysis_results, "chunks", "normalized_error_rate", testament_name)
    return analysis_results

def analyze_chapters(chapter_data_map: dict, testament_name: str, file_paths: dict):
    """PART 2: Analyzes aggregated results from each chapter and plots the absolute worst offenders."""
    print(f"\n--- Part 2: Analyzing Aggregated Chapters ({testament_name}) ---")
    chapter_results = []
    for chapter_name, chunks in sorted(chapter_data_map.items()):
        total_distance = sum(c.get('levenshtein_distance', 0) for c in chunks)
        total_length = sum(len(normalize_text(c.get('original_text', ''))) for c in chunks)
        raw_error_rate = total_distance / total_length if total_length > 0 else 1.0
        error_rate = min(1.0, raw_error_rate)
        chapter_results.append({"chapter": chapter_name, "aggregated_error_rate": error_rate})

    if not chapter_results: return None
    print(f"Analyzed {len(chapter_results)} chapters.")
    chapter_results.sort(key=lambda x: x['aggregated_error_rate'], reverse=True)
    
    plot_data = chapter_results[:MAX_CHAPTERS_TO_PLOT]
    ids = [res['chapter'] for res in plot_data]
    rates = [res['aggregated_error_rate'] for res in plot_data]
    title = f"Top {len(plot_data)} Worst Chapters by Error Rate ({testament_name})"
    _generate_sorted_bar_plot(ids, rates, "Chapter", title, file_paths['aggregate_plot'])

    file_paths['aggregate_json'].write_text(json.dumps(chapter_results, indent=4), encoding='utf-8')
    print(f"Aggregated chapter JSON report saved to: '{file_paths['aggregate_json']}'")
    print_threshold_analysis(chapter_results, "chapters", "aggregated_error_rate", testament_name)
    return chapter_results

def generate_flagged_list_report(results: list, item_type: str, id_key: str, value_key: str, error_threshold: float, testament_name: str, max_to_plot: int, file_paths: dict):
    """PART 3 & 4: Filters items by the manual threshold and generates sorted lists and plots."""
    print(f"\n--- Part {3 if item_type == 'Chunks' else 4}: Finding best {item_type} flagged with threshold > {error_threshold} ({testament_name}) ---")
    flagged_results = [r for r in results if r[value_key] > error_threshold]
    
    if not flagged_results:
        print(f"No {item_type.lower()} found with an error rate greater than {error_threshold}.")
        return

    print(f"Found {len(flagged_results)} {item_type.lower()} exceeding the threshold.")
    flagged_results.sort(key=lambda x: x[value_key], reverse=False)
    
    file_paths['flagged_json'].write_text(json.dumps(flagged_results, indent=4), encoding='utf-8')
    print(f"Sorted list of flagged {item_type.lower()} saved to: '{file_paths['flagged_json']}'")
    
    plot_data = flagged_results[:max_to_plot]
    ids = [res[id_key] for res in plot_data]
    rates = [res[value_key] for res in plot_data]
    title = f"Top {len(plot_data)} Best {item_type} Over Threshold ({error_threshold}) ({testament_name})"
    _generate_sorted_bar_plot(ids, rates, item_type.rstrip('s'), title, file_paths['flagged_plot'])

def _generate_distribution_plot(error_rates, testament_name, file_path):
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 7))
    sns.histplot(error_rates, kde=True, ax=ax, bins=50)
    ax.set_title(f'Distribution of Normalized Error Rate ({testament_name})', fontsize=16)
    ax.set_xlabel('Normalized Error Rate (Capped at 1.0)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    plt.tight_layout()
    plt.savefig(file_path)
    print(f"Distribution plot saved to: '{file_path}'")
    plt.close(fig)

def _generate_sorted_bar_plot(item_ids, error_rates, item_label, title, file_path):
    plt.style.use('seaborn-v0_8-whitegrid')
    height = max(10, len(item_ids) * 0.25)
    fig, ax = plt.subplots(figsize=(12, height))
    cmap = mcolors.LinearSegmentedColormap.from_list("grad", ["#ffdd77", "#d62728"])
    norm = mcolors.Normalize(vmin=min(error_rates) if error_rates else 0, vmax=max(error_rates) if error_rates else 1)
    bar_colors = list(cmap(norm(error_rates)))
    bars = sns.barplot(x=error_rates, y=item_ids, ax=ax, palette=bar_colors, orient='h')
    for bar in bars.patches:
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
                f'{bar.get_width():.3f}', ha='left', va='center', fontsize=8)
    ax.set_title(title, fontsize=16)
    ax.set_xlabel('Error Rate', fontsize=12)
    ax.set_ylabel(item_label, fontsize=12)
    ax.set_xlim(right=max(error_rates) * 1.15 if error_rates else 1)
    plt.tight_layout()
    plt.savefig(file_path)
    print(f"Sorted bar plot saved to: '{file_path}'")
    plt.close(fig)

def run_full_analysis(testament_name, all_chunk_data, chapter_data_map, error_threshold):
    """Orchestrates the complete 4-part analysis for a given dataset (OT or NT)."""
    print(f"\n{'='*20} RUNNING ANALYSIS FOR: {testament_name.upper()} {'='*20}")
    if not all_chunk_data:
        print(f"No data found for {testament_name}. Skipping analysis.")
        return

    # Define file paths for this specific analysis run
    file_paths = {
        'distribution_plot': OUTPUT_DIR / f"1_{testament_name}_individual_chunks_distribution.png",
        'distribution_json': OUTPUT_DIR / f"1_{testament_name}_individual_chunks_analysis.json",
        'aggregate_plot': OUTPUT_DIR / f"2_{testament_name}_chapter_level_comparison.png",
        'aggregate_json': OUTPUT_DIR / f"2_{testament_name}_chapter_level_analysis.json",
        'flagged_plot': OUTPUT_DIR / f"3_{testament_name}_best_chunks_over_threshold_{str(error_threshold).replace('.', '_')}.png",
        'flagged_json': OUTPUT_DIR / f"3_{testament_name}_chunks_over_threshold_{str(error_threshold).replace('.', '_')}.json",
        'flagged_chapters_plot': OUTPUT_DIR / f"4_{testament_name}_best_chapters_over_threshold_{str(error_threshold).replace('.', '_')}.png",
        'flagged_chapters_json': OUTPUT_DIR / f"4_{testament_name}_chapters_over_threshold_{str(error_threshold).replace('.', '_')}.json",
    }
    
    individual_results = analyze_individual_chunks(all_chunk_data, testament_name, file_paths)
    chapter_results = analyze_chapters(chapter_data_map, testament_name, file_paths)
    
    if individual_results:
        generate_flagged_list_report(individual_results, "Chunks", "chunk_id", "normalized_error_rate", error_threshold, testament_name, MAX_FLAGGED_CHUNKS_TO_PLOT, {'flagged_json': file_paths['flagged_json'], 'flagged_plot': file_paths['flagged_plot']})
    if chapter_results:
        generate_flagged_list_report(chapter_results, "Chapters", "chapter", "aggregated_error_rate", error_threshold, testament_name, MAX_CHAPTERS_TO_PLOT, {'flagged_json': file_paths['flagged_chapters_json'], 'flagged_plot': file_paths['flagged_chapters_plot']})

def main():
    """Main function to find, partition, and analyze all chunk results for OT and NT."""
    print("--- Starting Advanced Analysis and Report Generation ---")
    all_results_files = [p for p in OUTPUT_DIR.rglob("*.json") if p.parent.name != OUTPUT_DIR.name]
    if not all_results_files:
        print(f"Error: No individual chunk JSON files found in '{OUTPUT_DIR}' subdirectories.")
        return

    nt_chapter_map, ot_chapter_map = defaultdict(list), defaultdict(list)
    nt_chunk_data, ot_chunk_data = [], []
    uncategorized_count = 0

    for f in sorted(all_results_files):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            chapter_name = data.get("chapter")
            if not chapter_name: continue

            match = re.match(r'^([0-9]?[A-Za-z]+)', chapter_name)
            if not match:
                uncategorized_count += 1
                continue
            
            book_abbr = match.group(1)
            
            if book_abbr in NEW_TESTAMENT_BOOKS:
                nt_chapter_map[chapter_name].append(data)
                nt_chunk_data.append(data)
            elif book_abbr in OLD_TESTAMENT_BOOKS:
                ot_chapter_map[chapter_name].append(data)
                ot_chunk_data.append(data)
            else:
                uncategorized_count += 1
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Warning: Could not process file {f}: {e}")

    print(f"\n--- Data Partitioning Summary ---")
    print(f"Found {len(all_results_files)} total result files.")
    print(f"Assigned {len(nt_chunk_data)} files to New Testament.")
    print(f"Assigned {len(ot_chunk_data)} files to Old Testament.")
    if uncategorized_count > 0:
        print(f"Could not categorize {uncategorized_count} files.")
    
    # Run the complete analysis for each testament
    run_full_analysis("NT", nt_chunk_data, nt_chapter_map, ERROR_THRESHOLD_NT)
    run_full_analysis("OT", ot_chunk_data, ot_chapter_map, ERROR_THRESHOLD_OT)
    
    print("\n--- Analysis complete. ---")

if __name__ == "__main__":
    main()
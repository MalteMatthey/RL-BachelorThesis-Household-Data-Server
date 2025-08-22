import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

from . import config


# =============================================================================
# --- THESIS PLOT SETUP ---
# =============================================================================

def get_fig_size(width, fraction=1.0, height_scale=0.5):
    """
    Set figure dimensions to avoid scaling in LaTeX.
    """
    fig_width_pt = width * fraction
    inches_per_pt = 1 / 72.27
    fig_width_in = fig_width_pt * inches_per_pt
    fig_height_in = fig_width_in * height_scale
    return (fig_width_in, fig_height_in)


def setup_matplotlib_for_thesis(use_latex=True):
    """
    Sets up Matplotlib parameters and returns thesis-specific settings.
    """
    TEXTWIDTH_PT = 455.24411
    BASE_FONT_SIZE = 12

    # --- Your Custom Color Palette ---
    THESIS_COLORS = {
        'primary':       '#4664AA', # Mapped to "Real Error"
        'primary_light': '#BDDAFF',
        'secondary':     '#DF9B1B', # Mapped to "Synthetic Error"
        'tertiary':      '#009682',
    }

    font_sizes = {
        'font.size': BASE_FONT_SIZE,
        'axes.labelsize': BASE_FONT_SIZE - 1,
        'axes.titlesize': BASE_FONT_SIZE,
        'xtick.labelsize': BASE_FONT_SIZE - 2,
        'ytick.labelsize': BASE_FONT_SIZE - 2,
        'legend.fontsize': BASE_FONT_SIZE - 1, # Slightly larger legend font
        'figure.titlesize': BASE_FONT_SIZE,
    }

    if use_latex:
        plt.rcParams.update({
            "text.usetex": True,
            "font.family": "serif",
            "font.serif": ["Latin Modern Roman"],
            "text.latex.preamble": r"\usepackage{lmodern}\usepackage{amsmath}",
        })
    else:
        plt.rcParams.update({
            "text.usetex": False,
            "font.family": "serif",
            "font.serif": ["Latin Modern Roman", "Times New Roman"], # Fallback
        })
        
    plt.rcParams.update(font_sizes)
    plt.rcParams.update({
        'axes.grid': True,
        'grid.linestyle': ':',
        'grid.color': 'grey',
        'grid.alpha': 0.6,
        'lines.linewidth': 1.5,
        'lines.markersize': 4,
        'savefig.dpi': 300,
        'savefig.format': 'pdf',
        'savefig.bbox': 'tight',
    })
    
    return TEXTWIDTH_PT, THESIS_COLORS

# =============================================================================
# --- YOUR VALIDATION SCRIPT (with plotting logic corrected) ---
# =============================================================================

def validate_and_plot_results(
    synthetic_df: pd.DataFrame, 
    pre_2020_obs_df: pd.DataFrame,
    validation_year_df: pd.DataFrame, 
    output_dir: str,
    validation_label: str = "Validation"
):
    """
    Performs validation by comparing error characteristics of synthetic data against a hold-out set.
    """
    textwidth_pt, thesis_colors = setup_matplotlib_for_thesis()

    print(f"\n--- Running Validation and Plotting (Comparing Synthetic vs. {validation_label}) ---")
    
    plot_dir = os.path.join(output_dir, "validation_plots")
    os.makedirs(plot_dir, exist_ok=True)
    print(f"Saving validation plots to: {plot_dir}")

    # (Original data processing logic is unchanged)
    for col in config.WEATHER_FEATURES_TO_MODEL:
        synthetic_df[col] = pd.to_numeric(synthetic_df[col], errors='coerce')
        pre_2020_obs_df[col] = pd.to_numeric(pre_2020_obs_df[col], errors='coerce')

    synthetic_df['target_time_utc'] = pd.to_datetime(synthetic_df['target_time'], utc=True)
    pre_2020_obs_df['datetime_utc'] = pd.to_datetime(pre_2020_obs_df['datetime'], utc=True)
    
    merged_synthetic = pd.merge(
        synthetic_df,
        pre_2020_obs_df,
        left_on='target_time_utc',
        right_on='datetime_utc',
        suffixes=('_synth', '_obs')
    )

    if validation_year_df.empty or merged_synthetic.empty:
        print("Warning: Cannot perform validation due to empty data.")
        return

    for feature in config.WEATHER_FEATURES_TO_MODEL:
        merged_synthetic[f'{feature}_error'] = merged_synthetic[f'{feature}_synth'] - merged_synthetic[f'{feature}_obs']
    
    merged_synthetic['lead_time'] = (merged_synthetic['target_time_utc'] - pd.to_datetime(merged_synthetic['forecast_run'], utc=True)).dt.total_seconds() / 3600

    for feature in config.WEATHER_FEATURES_TO_MODEL:
        print(f"\nValidating feature: {feature}")
        
        real_errors = validation_year_df[f'{feature}_error'].dropna()
        synthetic_errors = merged_synthetic[f'{feature}_error'].dropna()

        if real_errors.empty or synthetic_errors.empty:
            print(f"  Skipping '{feature}' due to missing error data.")
            continue

        # --- MODIFIED PLOTTING BLOCK 1: Error Distribution ---
        fig_width, fig_height = get_fig_size(width=textwidth_pt, fraction=0.5, height_scale=0.9)
        fig, ax = plt.subplots(figsize=(fig_width, fig_height), constrained_layout=True)

        sns.histplot(real_errors, color=thesis_colors['primary'], label=f'Real {validation_label} Error', kde=True, stat='density', bins=50, ax=ax)
        sns.histplot(synthetic_errors, color=thesis_colors['secondary'], label='Synthetic Error', kde=True, stat='density', bins=50, ax=ax)
        
        ax.set_xlabel(f'{feature.capitalize()} Error')
        ax.set_ylabel('Density')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # --- CORRECTED LEGEND HANDLING ---
        # 1. Get handles and labels from the automatically created legend
        handles, labels = ax.get_legend_handles_labels()
        # 2. Remove the automatic legend from inside the plot
        if ax.get_legend():
            ax.get_legend().remove()
        # 3. Create a single, styled legend for the entire figure
        fig.legend(handles, labels, loc='outside lower center', ncol=2,
                   facecolor='whitesmoke', edgecolor='lightgray', framealpha=1)
        
        output_path = os.path.join(plot_dir, f'{feature}_error_dist_{validation_label}.pdf')
        plt.savefig(output_path)
        plt.close()

        # --- MODIFIED PLOTTING BLOCK 2: Error vs. Lead Time ---
        fig_width, fig_height = get_fig_size(width=textwidth_pt, fraction=0.5, height_scale=0.9)
        fig, ax = plt.subplots(figsize=(fig_width, fig_height), constrained_layout=True)

        sns.lineplot(data=validation_year_df, x='lead_time', y=f'{feature}_error', label=f'Real {validation_label} Error', errorbar='sd', color=thesis_colors['primary'], ax=ax)
        sns.lineplot(data=merged_synthetic, x='lead_time', y=f'{feature}_error', label='Synthetic Error', errorbar='sd', color=thesis_colors['secondary'], ax=ax)
        
        ax.set_xlabel('Lead Time [hours]')
        ax.set_ylabel(f'{feature.capitalize()} Error')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # --- CORRECTED LEGEND HANDLING ---
        handles, labels = ax.get_legend_handles_labels()
        ax.get_legend().remove()
        fig.legend(handles, labels, loc='outside lower center', ncol=2,
                   facecolor='whitesmoke', edgecolor='lightgray', framealpha=1)

        output_path = os.path.join(plot_dir, f'{feature}_error_vs_lead_{validation_label}.pdf')
        plt.savefig(output_path)
        plt.close()

        # (Original statistical test is unchanged)
        ks_stat, p_val = stats.ks_2samp(real_errors, synthetic_errors)
        print(f"  Kolmogorov-Smirnov Test (vs. {validation_label}): KS Stat={ks_stat:.4f}, p-value={p_val:.4f}")
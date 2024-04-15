# Initialize DataFrameProcessor with the folder containing JSON files
processor = DataFrameProcessor(r'C:\Users\jprib\OneDrive\Desktop\PhD\Meta-Analysis\json_files')

# Assign DataFrames based on terms
vasculature = processor.assign_dfs('Vascular')
# Continue similarly for other terms...

# Clean the DataFrames
vasculature_cleaned = processor.clean_dataframes(vasculature)
# Continue similarly for other DataFrames...

# Plot density graphs
processor.plot_density(vasculature_cleaned)

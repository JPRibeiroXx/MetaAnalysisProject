import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

class DataFrameProcessor:
    """
    A class for processing dataframes obtained from JSON files.

    Attributes:
    - json_folder_path (str): The path to the folder containing JSON files.
    - dfs (dict): A dictionary containing loaded dataframes.

    Methods:
    - __init__(json_folder_path): Initializes the DataFrameProcessor object.
    - load_dataframes(): Loads dataframes from JSON files.
    - assign_dfs(term): Assigns dataframes containing a given term in their filenames.
    - clean_dataframes(df): Cleans the given dataframe by removing duplicates, filling NaN values, and filtering by year.
    - search_phrase(df, phrase): Searches for a given phrase in the dataframe's 'title' column.
    - count_papers_per_year(df_unique): Counts the number of papers published per year.
    - plot_density(df_unique): Plots density and line plots of the number of papers published per year.
    - find_intersection(self, df_unique, intersection_terms): Find the intersection of papers based on boolean columns representing specified intersection terms.
    """

    def __init__(self, json_folder_path: str):
        """
        Initializes the DataFrameProcessor object.

        Args:
        - json_folder_path (str): The path to the folder containing JSON files.
        """
        self.json_folder_path = json_folder_path
        self.dfs = self.load_dataframes()

    def load_dataframes(self):
        """
        Loads dataframes from JSON files.

        Returns:
        - dfs (dict): A dictionary containing loaded dataframes.
        """
        json_files = [file for file in os.listdir(self.json_folder_path) if file.endswith('.jsonl')]
        dfs = {}
        for json_file in json_files: 
            query_name = json_file.split('.')[0]
            dfs[query_name] = pd.read_json(os.path.join(self.json_folder_path, json_file), lines=True)
        return dfs

    def assign_dfs(self, term: str):
        """
        Assigns dataframes containing a given term in their filenames.

        Args:
        - term (str): The term to search for in the filenames.

        Returns:
        - assigned_df (DataFrame): Concatenated dataframe containing dataframes with filenames containing the given term.
        """
        assigned_df = pd.concat([df for key, df in self.dfs.items() if term.lower() in key.lower()], ignore_index=True)
        return assigned_df

    def clean_dataframes(self, df):
        """
        Cleans the given dataframe by removing duplicates, filling NaN values, and filtering by year.

        Args:
        - df (DataFrame): The dataframe to be cleaned.

        Returns:
        - df_unique (DataFrame): The cleaned dataframe.
        """
        df_unique = df.drop_duplicates(subset='title', keep='first')
        df_unique.fillna({'abstract':'Not Available', 'doi':'Not Available', 'journal':'Not Available'}, inplace=True)
        df_unique['year'] = df_unique['date'].dt.year
        df_unique = df_unique[df_unique['year'] >= 2000]
        return df_unique

    def search_phrase(self, df, phrase: str):
        """
        Searches for a given phrase in the dataframe's 'title' column.

        Args:
        - df (DataFrame): The dataframe to search within.
        - phrase (str): The phrase to search for in the 'title' column.

        Returns:
        - DataFrame: Subset of the original dataframe containing rows with titles containing the given phrase.
        """
        return df[df['title'].str.contains(phrase, case=False, na=False)]

    def count_papers_per_year(self, df_unique):
        """
        Counts the number of papers published per year.

        Args:
        - df_unique (DataFrame): The cleaned dataframe.

        Returns:
        - count_df (DataFrame): DataFrame showing the count of papers published per year.
        """
        count_df = df_unique.groupby(['year', 'Query']).size().unstack().fillna(0)
        count_df.loc['Total'] = count_df.sum()
        return count_df

    def plot_density(self, df_unique):
        """
        Plots density and line plots of the number of papers published per year.

        Args:
        - df_unique (DataFrame): The cleaned dataframe.
        """
        fig, axes = plt.subplots(1, 2, figsize=(20, 8))
        sns.kdeplot(data=df_unique, x='year', hue='Query', linewidth=2.5, ax=axes[0])
        axes[0].set_title('Number of Papers Published per Year (Density Plot)')
        axes[0].set_xlabel('Year')
        axes[0].set_ylabel('Density')
        axes[0].grid(axis='y', linestyle='--', alpha=0.6)

        count_df = self.count_papers_per_year(df_unique)
        sns.lineplot(data=count_df.drop('Total'), linewidth=2.5, ax=axes[1], err_style="bars")
        axes[1].set_title('Number of Papers Published per Year (Line Plot)')
        axes[1].set_xlabel('Year')
        axes[1].set_ylabel('Number of Papers')
        axes[1].grid(axis='y', linestyle='--', alpha=0.6)
        axes[1].legend(title='Query', title_fontsize='large', fontsize='medium')

        plt.tight_layout()
        plt.show()
        
    def find_intersection(self, df_unique, intersection_terms: list):
        """
        Find the intersection of papers based on boolean columns representing specified intersection terms.

        Parameters:
        - df_unique (DataFrame): The DataFrame containing unique papers with boolean columns representing different queries.
        - intersection_terms (list): A list of strings representing the intersection terms.

        Returns:
        - DataFrame: A DataFrame containing papers that satisfy the intersection conditions.
        """
        # Define intersection column names based on provided terms
        intersection_columns = [term.replace(' ', '_') for term in intersection_terms]
        intersection_columns = [col for col in intersection_columns if col in df_unique.columns]

        # Check if any intersection columns exist in the DataFrame
        if not intersection_columns:
            print("No intersection columns found in DataFrame.")
            return pd.DataFrame()

        # Find rows where all intersection columns are True
        df_true = df_unique[df_unique[intersection_columns].all(axis=1)]
        return df_true

from paperscraper.pubmed import get_and_dump_pubmed_papers
import re

class PubMedScraper:
    """
    A class to facilitate searching and scraping PubMed for academic papers.
    """
    
    def __init__(self, search_terms: dict):
        """
        Initialize the PubMed Scraper.
        """
        self.search_terms = search_terms if search_terms is not None else {}
    
    def generate_queries(self, start_year: int, end_year: int, increment: int = 1):
        """
        Generate queries for PubMed search based on the provided search terms.
        Note: This query method makes a broad search for the terms, which will be later processed
        when we have the papers. There is a limit of 10,000 papers per JSON file. Ensure your
        searches and yearly gaps do not exceed this limit.
        
        Args:
            start_year (int): The start year for the date range.
            end_year (int): The end year for the date range.
            increment (int): The increment value for each date range.

        Returns:
            queries: A dictionary containing the generated queries.
        """
        queries = {} # Initiallize dictionary to store the queries
        date_range = {} # Initiallize dictionary to store the date ranges
       
        try:
            if not isinstance(start_year, int) or not isinstance(end_year, int) or not isinstance(increment, int):
                raise TypeError("Year values must be integers.")
            if start_year > end_year:
                raise ValueError("Start year cannot be greater than end year.")
            if increment <= 0:
                raise ValueError("Increment value must be greater than zero.")
       
        
            # Generate queries for each year in the date range
            if increment > 1:
                for dates in range (start_year,end_year,increment):
                    for key, value in self.search_terms.items():
                        date_dates = [f'"{dates}:{dates+increment-1}[dp]"']
                        queries[f'{key}_{dates}_{dates+increment-1}'] = [[value,date_dates]]
            else:    
                for dates in range (start_year,end_year,1):
                    for key, value in self.search_terms.items():
                        date_dates = [f'"{dates}:{dates}[dp]"']
                        queries[f'{key}_{dates}'] = [[value,date_dates]]
        except Exception as e:
               print(f"An error occurred while generating queries: {e}")  
               
        # Set the queries attribute
        self.queries = queries
        
        return self.queries

    def generate_search_strings(self):
        """
        Generate search strings based on the provided queries.

        Returns:
            dict: A dictionary containing the search strings for each set of queries.
        """
        
        def create_search_string(terms):
            # Join terms in each sublist with 'OR', and then join the sublists with 'AND'
            return ' AND '.join(['(' + ' OR '.join(sublist) + ')' for sublist in terms])

        
        try:
            search_strings = {key: [create_search_string(query) for query in value] for key, value in self.queries.items()}
            return search_strings
        except Exception as e:
            print(f"An error occurred while generating search strings: {e}")
        return None
    
    def scrape_pubmed(self):
        """
        Scrape PubMed for papers based on the generated queries.
        
        Args:
            self.queries (dict): A dictionary containing the generated queries.
        """
        
        def sanitize_filename(filename):
            # Remove any characters that are not alphanumeric or underscores
            return re.sub(r'[^\w]', '_', filename)
        
        try:
            if not self.queries:
                raise ValueError("No queries generated. Please generate queries before scraping PubMed.")

            for query_name, query_list in self.queries.items():
                # Sanitize the query_name for use in the file path
                sanitized_query_name = sanitize_filename(query_name)
                for query in query_list:
                    get_and_dump_pubmed_papers(query, output_filepath=f'./json_files/{sanitized_query_name}_PubMed.jsonl')
            print('Done!')
        except Exception as e:
            print(f"An error occurred while scraping PubMed: {e}")


                
 

    
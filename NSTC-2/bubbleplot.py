import os 
import pandas as pd 
import argparse 
import folium 
import requests 
import json 
from statistics import median, mode 
from requests.adapters import HTTPAdapter, Retry 

def extract_postal_code(case_location): 
    case_location = str(case_location) 
    if len(case_location) < 6: 
        return None 
    return case_location[-6:] 

def extract_block(case_location): 
    case_location = str(case_location) 
    if len(case_location) < 4: 
        return None 
    return case_location[:4] 

def main(input_file, output_csv, output_html, prefix, month, year, min_count): 
    df = pd.read_csv(input_file, encoding='ISO-8859-1') 
   
    # Extract postal codes and blocks 
    df['Postal.Code'] = df['Case Location'].apply(extract_postal_code) 
    df['Block'] = df['Case Location'].apply(extract_block) 
   
    # Count occurrences of postal codes 
    df_count = df['Postal.Code'].value_counts().reset_index() 
    df_count.columns = ['Postal.Code', 'Count'] 
   
    # Calculate Mean, Median, and Mode Counts 
    mean_count = df_count['Count'].mean() 
    median_count = median(df_count['Count']) 
    mode_counts = mode(df_count['Count']) 
    
    # Merge block information into df_count 
    df_merged = df_count.merge(df[['Postal.Code', 'Block']].drop_duplicates(), on='Postal.Code', how='left') 
   
    # Filter out postal codes with counts less than the user-specified minimum count 
    df_merged = df_merged[df_merged['Count'] >= int(min_count)] 
   
    # Initialize longitude and latitude columns 
    df_merged['OnemapLongitude'] = 0.0 
    df_merged['OnemapLatitude'] = 0.0 
    
    # Configure retry strategy for requests 
    retry_strategy = Retry( 
        total=3, 
        backoff_factor=1, 
        status_forcelist=[429, 500, 502, 503, 504], 
        allowed_methods=["HEAD", "GET", "OPTIONS"] 
    ) 

    adapter = HTTPAdapter(max_retries=retry_strategy) 
    http = requests.Session() 
    http.mount("https://", adapter) 

    # Iterate over each row and update longitude and latitude 
    for i in range(len(df_merged)): 
        postal_code = df_merged.loc[i, 'Postal.Code'] 
        try: 
            url = f'https://www.onemap.gov.sg/api/common/elastic/search?searchVal={postal_code}&returnGeom=Y&getAddrDetails=Y&pageNum=1' 
            req = http.get(url) 
            req.raise_for_status() 
            jdata = json.loads(req.text) 
            if jdata['found'] >= 1: 
                df_merged.loc[i, 'OnemapLongitude'] = float(jdata['results'][0]['LONGITUDE']) 
                df_merged.loc[i, 'OnemapLatitude'] = float(jdata['results'][0]['LATITUDE']) 
            else: 
                df_merged.loc[i, 'OnemapLongitude'] = float('nan') 
                df_merged.loc[i, 'OnemapLatitude'] = float('nan') 

        except requests.exceptions.RequestException as e: 
            df_merged.loc[i, 'OnemapLongitude'] = float('nan') 
            df_merged.loc[i, 'OnemapLatitude'] = float('nan') 
   
    # Create a base map centered based on prefix 
    if prefix == 'NSL': 
        center = [1.4248671, 103.8490735] 
    elif prefix == 'CP': 
        center = [1.4336331, 103.8352494] 
    elif prefix == 'NSS': 
        center = [1.4172761, 103.8375479] 
    elif prefix == 'NSC': 
        center = [1.423678, 103.8340208] 
    elif prefix == 'NSE': 
        center = [1.4300711, 103.8423965] 
    else: 
        center = [1.4259, 103.8482]  # Default center if prefix not recognized 
     

    # Create a base map 
    m = folium.Map(location=center, zoom_start=16) 

    # Add bubbles and markers to the map 
    for _, row in df_merged.iterrows(): 
        if pd.notna(row['OnemapLatitude']) and pd.notna(row['OnemapLongitude']): 
            redcount = int(min_count) + 1 
            color = 'red' if row['Count'] > redcount else 'blue' 
            tooltip = folium.Tooltip(f"Postal Code:<b> {row['Postal.Code']}</b><br> Cases:<b> {row['Count']}</b><br> Block:<b> {row['Block']}</b>") 
            
            # scaling the bubble size depending on min_count input from user             
            if int(min_count) < 6: 
                redmux = 3 - 0.7*(int(min_count) - 3) 
            else: 
                redmux = 1  
             
            # Add the circle marker for the bubble 
            circle_marker = folium.CircleMarker( 
                location=[row['OnemapLatitude'], row['OnemapLongitude']], 
                radius=row['Count'] * redmux,  # Adjust radius 
                color=color, 
                fill=True, 
                fill_color=color, 
                fill_opacity=0.3, 
                tooltip=tooltip 
            ) 

            circle_marker.add_to(m) 
           

            # Add the marker for block information slightly above the bubble 
            if color == 'red':  # Only for red bubbles 
                block_marker = folium.Marker( 
                    location=[row['OnemapLatitude'] + 0.0001, row['OnemapLongitude'] - 0.0001],  # Adjust position 
                    icon=folium.DivIcon(html=f"<div style='font-size: 10pt;'><b>{row['Block']}</b></div>") 
                ) 

                block_marker.add_to(m) 
   
    # Add legend 
    legend_html = f''' 
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 130px; height: 180px; 
                    background-color: white; z-index:9999; font-size:12px; 
                    border:2px solid grey; border-radius:6px; 
                    "> 

        &nbsp; <b>{prefix} {month} {year}</b> <br> 
        &nbsp; <br> 
        &nbsp; <b>Legend</b> <br> 
        &nbsp; <i class="fa fa-circle" style="color:red"></i>&nbsp; > {int(min_count) + 1} cases <br> 
        &nbsp; <i class="fa fa-circle" style="color:blue"></i>&nbsp; {int(min_count)} or  {int(min_count) + 1} cases <br> 
        <br> 
        &nbsp; <b>Statistics</b> <br> 
        &nbsp; Mean Count: {mean_count:.2f} <br> 
        &nbsp; Median Count: {median_count} <br> 
        &nbsp; Mode Count: {mode_counts} <br> 

        </div> 

    ''' 

    m.get_root().html.add_child(folium.Element(legend_html)) 

    # Save the map to an HTML file 
    m.save(output_html) 
    

    # Save the updated DataFrame to a new CSV file 
    df_merged.to_csv(output_csv, index=False) 

if __name__ == '__main__': 

    parser = argparse.ArgumentParser(description='Process postal codes and generate bubble plot.') 
    parser.add_argument('--input', required=True, help='Input CSV file path') 
    parser.add_argument('--output_csv', required=True, help='Output CSV file path') 
    parser.add_argument('--output_html', required=True, help='Output HTML file path') 
    parser.add_argument('--prefix', required=True, help='Prefix selected by user') 
    parser.add_argument('--month', required=True, help='Month selected by user')
    parser.add_argument('--year', required=True, help='Year selected by user')
    parser.add_argument('--min_count', required=True, help='Minimum count of cases to be included') 
    args = parser.parse_args() 
    main(args.input, args.output_csv, args.output_html, args.prefix, args.month, args.year, args.min_count) 

 

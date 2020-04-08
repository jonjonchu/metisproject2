'''
Jonathan L Chu, for Metis Data Science, 7 April 2020

Methods for scraping and downloading movie data from
www.boxofficemojo.com. Actual pipline can be found in the
accompanying boxOfficeMojoPipeline.py file.
'''

from bs4 import BeautifulSoup
import requests
import pandas as pd
import re
import dateutil.parser
import datetime
import time


def get_dataframe_from_year(year, num_releases=-1):
    '''
    Method to retrieve movie data from one year of
    www.boxofficemojo.com/year/

    Number of releases defaults to all [0:-1]

    Note that the execution time is equal to 
    2 * len(releases in the year) + 1 seconds

    Returns pandas dataframe
    '''
    df = pd.DataFrame()
    website = 'https://www.boxofficemojo.com'
    title_url_suffix = 'credits/?ref=bo_tt_tab'

    year_url = website + '/year/' + str(year)
    # Get list of release url suffixes
    release_urls = get_release_urls_from_year(year_url, num_releases)

    time.sleep(1)
    # Get data for each film in list of release_urls
    for release_suffix in release_urls:
        # Transform release url to title url
        release_url = website + release_suffix
        title_id = get_title_url_from_release(release_url)
        if title_id is not None:
            title_url = website + title_id + title_url_suffix

            time.sleep(1)
            # Obtain Movie data
            data = get_movie_info_from_title(title_url)
            df = df.append(data)
            print('dataframe shape: ', df.shape)
            time.sleep(1)

    df = df.reset_index()
    return df


def get_release_urls_from_year(year_url, number= -1):
    '''
    Takes a URL for a particular year on boxofficemojo.com 
    i.e. https://www.boxofficemojo.com/year/2020/?ref_=bo_yl_table_1
    
    Returns a list of URLs suffixes of all releases from that year
    N.B.: please prepend 'www.boxofficemojo.com' to all returned URLs
    
    Number of releases defaults to all [0:-1]

    Sample output: 
    ['/release/rl1182631425/?ref_=bo_yld_table_1',
     '/release/rl2969994753/?ref_=bo_yld_table_2',
     '/release/rl4244997633/?ref_=bo_yld_table_3',
     '/release/rl755467777/?ref_=bo_yld_table_4',
     ...
    ]
    '''
    release_urls = []
    
    response = requests.get(year_url)
    print(response.status_code, ' ', year_url)
    page = response.text
    soup = BeautifulSoup(page, "lxml")
    del response, page
    
    for row in soup.find('div', id='table').find('table').find_all('tr')[1:]:
        release_url = row.find(class_='a-link-normal')['href']
        release_urls.append(release_url)
    
    return release_urls[0:number]


def get_title_url_from_release(release_url):
    '''
    Takes a URL for a particular release on boxofficemojo.com 
    i.e. https://www.boxofficemojo.com/release/rl4244997633/
    
    Returns the URL suffix for the title associated with the release_url
    N.B.: please prepend 'www.boxofficemojo.com' to all returned URLs
    
    Sample output: '/title/tt3794354/'
    '''
    response = requests.get(release_url)
    print(response.status_code, ' ', release_url)
    page = response.text
    soup = BeautifulSoup(page, "lxml")
    del response, page
    title_link = soup.find(
        'a', class_="a-link-normal mojo-title-link refiner-display-highlight")
    if title_link is not None:
        title = title_link['href']
        title = title.split('?ref_')[0]
        return title
    else:
        return None


def get_movie_info_from_title(url):
    '''
    Parse the following data from a boxofficemojo.com Title url: 
    ['Movie_Title','Domestic_Distributor','Domestic_Total_Gross',
    'Runtime','Rating','Release_Date','Budget', 'Cast1','Cast2','Cast3','Cast4']
    
    Input: boxofficemojo.com url like:
    'https://www.boxofficemojo.com/title/tt0848228/credits/?ref_=bo_tt_tab'
    Needs to have 'credits/?ref_=bo_tt_tab' in url after title id
    
    Returns [{}] ready for appending to a pandas DataFrame

    Sample output: 
    [{'Movie_Title': 'Sonic the Hedgehog',
     'Domestic_Distributor': 'Paramount Pictures',
     'Domestic_Total_Gross': 146066470,
     'Runtime': 99,
     'Rating': 'PG',
     'Release_Date': datetime.datetime(2020, 2, 12, 0, 0),
     'Budget': 85000000,
     'Cast1': 'Ben Schwartz',
     'Cast2': 'James Marsden',
     'Cast3': 'Jim Carrey',
     'Cast4': 'Tika Sumpter'}
    ]
    
    '''

    headers = ['Movie_Title', 'Domestic_Distributor', 'Domestic_Total_Gross',
               'Runtime', 'Rating', 'Release_Date', 'Budget', 'Cast1', 'Cast2', 'Cast3', 'Cast4']
    movie_data = []

    response = requests.get(url)
    print(response.status_code, ' ', url)
    page = response.text
    soup = BeautifulSoup(page, "lxml")
    del page, response

    # title
    title = soup.find('title').text.split('-')[0].strip()

    # domestic distributor
    if get_movie_value(soup, 'Domestic Distributor') is not None:
        distributor = get_movie_value(soup, 'Domestic Distributor').split('See')[0]
    else: distributor = None

    # domestic total gross
    if soup.find(class_='mojo-performance-summary-table').find_all('span', class_='money') is not None:
        raw_domestic_total_gross = (soup.find(class_='mojo-performance-summary-table')
                                    .find_all('span', class_='money')[0].text)
        domestic_total_gross = money_to_int(raw_domestic_total_gross)
    else: domestic_total_gross = None 

    # runtime
    raw_runtime = get_movie_value(soup, 'Running')
    runtime = runtime_to_minutes(raw_runtime)

    # rating
    rating = get_movie_value(soup, 'MPAA')

    # release date
    raw_release_date = get_movie_value(soup, 'Release Date').split('\n')[0]
    release_date = to_date(raw_release_date)

    # Budget
    raw_budget = get_movie_value(soup, 'Budget')
    budget = money_to_int(raw_budget)

    # Get Cast info
    if soup.find(id="principalCast") is not None:
        castInfo = soup.find(id="principalCast").find_all('tr')
    else: castInfo = []

    if len(castInfo) > 1:
        cast1 = castInfo[1].text.split('\n')[0]
    else: cast1 = None
    if len(castInfo) > 2:
        cast2 = castInfo[2].text.split('\n')[0]
    else: cast2 = None
    if len(castInfo) > 3:
        cast3 = castInfo[3].text.split('\n')[0]
    else: cast3 = None
    if len(castInfo) > 4:
        cast4 = castInfo[4].text.split('\n')[0]
    else: cast4 = None

    movie_dict = dict(zip(headers, [title,
                                    distributor,
                                    domestic_total_gross,
                                    runtime,
                                    rating,
                                    release_date,
                                    budget,
                                    cast1,
                                    cast2,
                                    cast3,
                                    cast4]))

    movie_data.append(movie_dict)
    return movie_data


def get_movie_value(soup, field_name):
    '''Grab a value from Box Office Mojo HTML
    
    Takes a string attribute of a movie on the page and returns the string in
    the next sibling object (the value for that attribute) or None if nothing is found.
    '''

    obj = soup.find(text=re.compile(field_name))

    if not obj:
        return None

    # this works for most of the values
    next_element = obj.findNext()

    if next_element:
        return next_element.text
    else:
        return None


def money_to_int(moneystring):
    if moneystring is not None:
        moneystring = moneystring.replace('$', '').replace(',', '')
        return int(moneystring)
    else: return None


def runtime_to_minutes(runtimestring):
    try:
        runtime = runtimestring.split()
        minutes = int(runtime[0])*60 + int(runtime[2])
        return minutes
    except:
        return None


def to_date(datestring):
    date = dateutil.parser.parse(datestring)
    return date

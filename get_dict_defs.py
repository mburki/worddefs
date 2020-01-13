
#!/usr/bin/env python3

# Copyright (c) 2020 Manuel Burki
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests
import json
import os
import time
import re
import logging
import configparser

# Configuration Variables

config = configparser.ConfigParser()
config.read('config.ini')

app_id      = config['DictAPI']['app_id']
app_key     = config['DictAPI']['app_key']
lang        = config['DictAPI']['lang']
in_file     = config['DictAPI']['in_file']
out_file    = config['DictAPI']['out_file']
error_file  = config['DictAPI']['error_file']
divider     = config['DictAPI']['divider']
throt_secs  = int(config['DictAPI']['throt_secs'])

base_url    = 'https://od-api.oxforddictionaries.com:443'
entries_url = base_url + '/api/v2/entries/'
lemmas_url  = base_url + '/api/v2/lemmas/'
gen_error   = 'An error has occured.'

logging.basicConfig(format='%(asctime)s %(levelname)s - %(message)s', level=logging.INFO)

# End of Configuration
    
def extract_def_from_dict(status_code, response):

    try:
        definition_dict = json.loads(response.text)
    except:
        pass

    if status_code == 200:
        try:
            definition = definition_dict['results'][0]['lexicalEntries'][0]['entries'][0]['senses'][0]['definitions'][0]
        except KeyError:
            try:
                _, definition = get_definition(definition_dict['results'][0]['lexicalEntries'][0]['entries'][0]['senses'][0]['crossReferences'][0]['text']) 
            except:
                definition = gen_error
    else:
        definition = gen_error

    return definition


def get_definition(word):

    response = requests.get(entries_url + lang + '/' + word.lower(), headers = {'app_id' : app_id, 'app_key' : app_key})

    if response.status_code != 200:    
        response = requests.get(lemmas_url + lang + '/' + word.lower(), headers = {'app_id' : app_id, 'app_key' : app_key})

        if response.status_code == 200:
            lemma_dict = json.loads(response.text)
            lemmaword = lemma_dict['results'][0]['lexicalEntries'][0]['inflectionOf'][0]['text']
            response = requests.get(entries_url + lang + '/' + lemmaword.lower(), headers = {'app_id' : app_id, 'app_key' : app_key})
            definition = extract_def_from_dict(response.status_code, response)
        else:
            definition = extract_def_from_dict(response.status_code, response)
    else:
        definition = extract_def_from_dict(response.status_code, response)  

    if definition == gen_error:
        status_code = 510
    else:
        status_code = response.status_code

    return status_code, definition


def do_backup():

    curr_time = time.strftime('%Y%m%d-%H%M%S')

    if os.path.exists(out_file):
        logging.info('Backing up ' + out_file)
        os.rename(out_file,re.sub(r"\.[a-zA-Z0-9]+$", '', out_file) + '_' + curr_time + '.bak')

    if os.path.exists(error_file):
        logging.info('Backing up ' + error_file)
        os.rename(error_file,re.sub(r"\.[a-zA-Z0-9]+$", '', error_file) + '_' + curr_time + '.bak')   


def process_data():

    wordlist = list()
    errorlist = list()
    load_count = succ_count = err_count = 0

    logging.info('Reading data input file for processing.')
    with open(in_file, 'r') as i:
        for line in i:
            wordlist.append(line.rstrip('\n'))
            load_count += 1

    logging.info(str(load_count) + ' word(s) loaded from input file.')

    with open(out_file, 'w+') as o:
        for entry in wordlist:
            time.sleep(throt_secs)
            logging.info('Retrieving definition from API for ' + entry)
            status_code, definition = get_definition(entry)

            if status_code == 200:
                logging.info('Definition for ' + entry + ' retrieved successfully.')
                o.write(entry + divider + definition + '\n')
                succ_count += 1
            else:
                logging.error('Failed to retrieve definition for ' + entry + ' - ErrorCode: ' + str(status_code) + ' - ' + definition)
                errorlist.append(entry)
                err_count += 1
    
    logging.info('Saving dead letter queue to ' + error_file)
    with open(error_file, 'w+') as e:
        for error in errorlist:
            e.write(error + '\n')

    now = time.strftime('%Y%m%d-%H%M%S')
    logging.info('Backing up processed data file.')
    os.rename(in_file,re.sub(r"\.[a-zA-Z0-9]+$", '', in_file) + '_' + now + '.csv')  
    logging.info('STATISTICS: ' + str(load_count) + ' word(s) loaded - ' 
                                + str(succ_count) + ' definition(s) retrieved - ' 
                                + str(err_count) + ' error(s).')


if __name__ == '__main__':

    logging.info('Starting to process data.')
    do_backup()
    process_data()
    logging.info('Exiting program.')
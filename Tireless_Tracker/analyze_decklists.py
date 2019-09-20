import argparse
import requests
import os
import pandas as pd
from collections import defaultdict
import numpy as np
import datetime
from matplotlib import rc
rc('font', **{'family': 'serif', 'serif': ['Computer Modern']})
rc('text', usetex=True)
import matplotlib.pyplot as plt

def fetch_cards():
    '''Fetches the default cards from Scryfall'''

    print('Fetching cards from Scryfall...')
    resp = requests.get('https://archive.scryfall.com/json/scryfall-default-cards.json')
    json_data = resp.json()
    magic_cards = {}
    for i in range(len(json_data)):
        card_name = json_data[i]['name']
        if card_name not in magic_cards.keys():
            magic_cards[card_name] = {'color': ''.join(json_data[i]['color_identity']),
                                      'cmc': json_data[i]['cmc'],
                                      'type': json_data[i]['type_line']}

    
        if json_data[i]['layout'] == 'transform': magic_cards[card_name.split('//')[0].strip(' ')] = magic_cards[card_name]

    return magic_cards

def make_deck(infile):

    '''Given a deck text file, analyze its contents. Outputs the main/sideboard rate of cards, the win/loss, deck colors, archetypes'''

    maindeck, side = [], []

    with open(infile) as deck_file:

        summary = [line.strip('\n') for line in deck_file.readlines()]
        deck_color = summary[0].split(':')[1].strip(' ')
        deck_archetypes = summary[1].split(':')[1].strip(' ').split('_')
        deck_record = map(float,summary[3].split(':')[1].strip(' ').split('-'))
        
        cards = []
        for card_info in summary[5:]:
            card_info = card_info.strip('\n')
            if card_info == '':
                cards.extend([card_info])
                continue
            else:
                num, card = card_info.split(' ')[0],' '.join(card_info.split(' ')[1:])
                cards.extend([card]*int(num))
        try:
            div = cards.index('')
            maindeck, side = cards[:div], cards[div+1:]
        except:
            maindeck = cards
            side = []
        win, loss = deck_record

    return maindeck, side, deck_color, deck_archetypes, win, loss

def extract_decklists(directory, magic_cards, date_arg):

    '''Parses all the decklists in a directory and creates a dictionary to contain this info.'''
    misspellings = open('misspellings.txt', 'w')
    misspellings.write('The following cards are not found in Scryfall\'s database:\n')
    deck_dict = {}

    for i, infile in enumerate(os.listdir(directory)):

        if infile[-4:] != '.txt': continue # added to avoid '.DS_store', etc

        try:
            maindeck, side, color, archetypes, win, loss = make_deck(os.path.join(directory,infile))
            
            if date_arg:
                date = infile.split('_')[-1][:-4]
        except:
            print('File {} could not be analyzed.'.format(infile))
            continue

        for card in maindeck + side: 
            if not magic_cards.get(card): 
                misspellings.write('{} in file {}\n'.format(card, infile))

        deck_dict[i] = {'main': maindeck, 'side': side, 'color': color, 'archetypes': archetypes, 'record':[win, loss]}
        if date_arg: deck_dict[i]['date'] = date

    return deck_dict

def find_card_type(full_type):
    
    '''Takes in a card_type (str) and returns its shortened type (Artifact, Creature, Enchantment, PW, Land, Sorcery, Instant)'''

    for card_type in ['Creature', 'Artifact', 'Enchantment', 'Planeswalker', 'Land', 'Sorcery', 'Instant']:
        if card_type in full_type:
            return card_type

    return None

def export_card_analysis(deck_list_dict, magic_cards, card_filter):
    
    '''Analyzes card representation and win rates and exports them to csv'''
    
    card_dict = {}
    for deck_dict in deck_list_dict.values():
        deck = deck_dict['main']
        win, loss = map(int, deck_dict['record'])
        for card in deck:

            if not magic_cards.get(card): continue

            if card not in card_dict.keys():
                card_dict[card] = {'win': win, 'loss': loss, 'num': 0}
            else:
                card_dict[card]['num'] += 1
                card_dict[card]['win'] += win
                card_dict[card]['loss'] += loss

    print('{} unique cards identified in decklists'.format(len(card_dict)))

    for card in card_dict.keys():
        color, cmc, card_type = magic_cards[card].values()

        for characteristic, value in zip(['color', 'cmc', 'type'], [color, cmc, find_card_type(card_type)]):
            card_dict[card][characteristic] = value

    results = {card: {key: card_dict[card][key] for key in ['win', 'loss', 'num', 'color', 'cmc', 'type']} for card in card_dict.keys()}
    results_df = pd.DataFrame.from_dict(results, orient = 'index').reset_index()
    results_df.columns = ['Name','Win', 'Loss','Num','Color', 'CMC', 'Type']
    results_df['Win %'] = results_df['Win']/(results_df['Win'] + results_df['Loss'])
    if card_filter:
        results_df = results_df.loc[results_df['Num'] > card_filter]
    results_df.to_csv('Card_Decklist_Analysis.csv', index = False)

def export_archetype_analysis(deck_list_dict):
    
    '''Analyzes archetype distribution and exports to csv. Will analyze by subtypes as well.'''
    
    archetype_dict = super_archetypes = defaultdict(lambda: {'num':0, 'win': 0, 'loss': 0})

    archetypes = []
    for deck_dict in deck_list_dict.values():
        wins, losses = map(int, deck_dict['record'])

        archetypes.extend(deck_dict['archetypes'])        
        if len(deck_dict['archetypes']) == 1: string = 'Pure'
        for archetype in deck_dict['archetypes']:

            archetype_dict[archetype]['num'] += 1
            archetype_dict[archetype]['win'] += wins
            archetype_dict[archetype]['loss'] += losses

    archetype_df = pd.DataFrame.from_dict(archetype_dict, orient = 'index').reset_index()
    archetype_df.columns = ['Archetype','Num','Win', 'Loss']
    archetype_df['Win %'] = archetype_df['Win']/(archetype_df['Win'] + archetype_df['Loss'])
    archetype_df.to_csv('Archetype_Analysis.csv', index = False)


def export_color_analysis(deck_dict, magic_cards):

    '''Analyze color distribution in cards and decks and exports to csv'''

    deck_colors, card_colors = [], defaultdict(lambda: [])
    for deck in deck_dict.values():
        
        main_colors = [magic_cards[card]['color'] for card in deck['main'] if magic_cards.get(card) and find_card_type(magic_cards[card]['type']) != 'Land']
        deck_colors.extend(list(deck['color']))
        colors, counts = np.unique(main_colors, return_counts = True)
        counts = counts/sum(counts)
        color_dict = dict(zip(colors, counts))
        for color, count in color_dict.items():
            if count > 0.15: card_colors[color].append(count)

    deck_color, deck_num = np.unique(deck_colors, return_counts = True)
    card_colors = {color:np.average(counts) for color, counts in card_colors.items()}

    color_df = pd.DataFrame.from_dict(dict(zip(deck_color, deck_num/sum(deck_num))), orient = 'index').reset_index()
    color_df.columns = ['Color','Deck_Spread']
    color_df['Card_Spread'] = [card_colors[color] for color in deck_color]
    color_df.to_csv('Color_Analysis.csv', index = False)

def export_timecourse_analysis(deck_dict, window):
    decklists = deck_dict.values()
    archetypes = [deck['archetypes'] for deck in decklists]
    archetypes = list(set([archetype for archetype_list in archetypes for archetype in archetype_list]))
    dates = [deck['date'] for deck in decklists]

    sorted_decklists = [deck for _, deck in sorted(zip(dates,decklists), key=lambda pair: datetime.datetime.strptime(pair[0], "%m%d%Y"))]
    window_num = len(sorted_decklists) - window + 1
    storage_matrix = np.zeros([len(archetypes), window_num])
    for i in range(window_num):
        decklist_window = sorted_decklists[i:i+window]
        for j, archetype in enumerate(archetypes):
            records = np.array([deck['record'] for deck in decklist_window if archetype in deck['archetypes']])
            storage_matrix[j, i] = np.sum(records, axis = 0)[0]/np.sum(records)

    return archetypes, storage_matrix

def plot_timecourse(archetypes, storage_matrix):

    fig, ax = plt.subplots(1,1, figsize = (10,6))
    colors = {'Aggro':'#ffa600', 'Midrange':'#bc5090', 'Control':'#003f5c'}
    for i, archetype in enumerate(archetypes):
        if archetype in ['Reanimator', 'Combo', 'Ramp']: continue
        data = storage_matrix[i, :]
        ax.plot(range(len(data)), data, label = '{}'.format(archetype), color = colors[archetype])

    ax.legend(fontsize = 14)
    plt.xlabel('Decks', fontsize = 18)
    plt.ylabel('Rolling Average', fontsize = 18)
    plt.xticks(fontsize = 14)
    plt.yticks(fontsize = 14)
    plt.title('Archetype Winrates', fontsize = 18)
    plt.tight_layout()
    fig.savefig('Archetype_Winrates.png', dpi = 300)

def main():
    parser = argparse.ArgumentParser(description='Analyzes decklists given an input folder')
    parser.add_argument('-d','--deck_folder', type=str, metavar='\b', help = 'folder containing decklist text files', required = True)
    parser.add_argument('-f','--filter', type=int, metavar='\b', help = 'cards with frequency below this filter will be excluded'
                        , default = 0)
    parser.add_argument('-date','--date', type=bool, metavar='\b', help = 'if your decklist names have date information, will perform timecourse analysis of archetypes'
                        , default = False)
    parser.add_argument('-w', '--window', type=int, metavar = '\b', help = 'size of sliding window in time course analysis', default = 100)
        
    args = parser.parse_args()

    decklist_folder = args.deck_folder
    card_filter = args.filter
    date_arg = args.date
    window = args.window

    magic_cards = fetch_cards()
    deck_dict = extract_decklists(decklist_folder, magic_cards, date_arg)
    print('{} decks extracted.'.format(len(deck_dict)))

    export_card_analysis(deck_dict, magic_cards, card_filter)
    export_archetype_analysis(deck_dict)
    export_color_analysis(deck_dict, magic_cards)
    
    if date_arg: 
        archetypes, timecourse = export_timecourse_analysis(deck_dict, window)
        plot_timecourse(archetypes, timecourse)

if __name__ == '__main__':
    main()
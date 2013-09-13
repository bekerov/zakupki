import re
from lxml import etree
from datetime import datetime, timedelta

from transform import *
from utils import *

def contracts_etl(ftp, collection, update_type):
	'''
		Get a list of files for each region, append to list.

		Load and parse files, for each file call transform,
		then load each document updating metadata.
	'''
	# Build file list
	print ts(), 'Building file list'
	re_file = re.compile('.*\..*') # filter folders
	folders = (name for name in ftp.nlst() if not re_file.match(name))
	files = []
	for region in folders:
		print ts(), region
		region_files = inc_files(collection, ftp, region) if update_type == 'inc' else all_files(collection, ftp, region)
		files.extend([(f, region) for f in region_files])
	size = 0.0
	# for (f, region) in files:
	# 	size += ftp.size(f)
	print ts(), 'Loading {len} files, {size} Mb total'.format(len=len(files), size=round(size / (1024 * 1024), 2))
	# inserting files
	meta = collection.database[collection.name + '_meta']
	for (f, region) in files:
		print ts(), f
		xml_file = extract(ftp, f)
		if xml_file:
			for event, xml in etree.iterparse(xml_file, tag='{http://zakupki.gov.ru/oos/export/1}contract'):
				if event == 'end':
					document = transform_contract(xml)
					document['folder_name'] = region
					xml.clear()
					load(collection, document, upsert=True)
					meta.update({'folder_name': region, 'max_date': {'$lt': document['publish_date'] } }, {'$set': {'max_date': document['publish_date'] } })

def products_etl(ftp, collection, update_type):
	if update_type == 'all':
		mask = '*.xml.zip'
	else:
		mask = 'nsiProduct_inc_*.xmp.zip'
	ftp.cwd('/auto/product')
	files = ftp.nlst(mask)
	for f in files:
		xml_file = extract(ftp, f)
		if xml_file:
			for event, xml in etree.iterparse(xml_file, tag='{http://zakupki.gov.ru/oos/types/1}nsiProduct'):
				if event == 'end':
					document = transform_product(xml)
					load(collection, document, upsert=True)
					xml.clear()
			
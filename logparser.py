#!/usr/bin/env python3

import os
import sys
import re
import xlsxwriter

match_series_dict = {
  'series' : {
    'allocation efficiency test:': 'Allocation',
    'list traverse test:': 'Traverse'
  }
}

# each element in a list: (regex, groupname)
# if regex is empty, groupname is used to search in match_series_dict
match_orders = [
  ('', 'series'),
  (r'Node size (?P<NodeSize>\d+):', 'NodeSize'),
  (r'length: (?P<ListLength>\d+), #iteration: (?:\d+)', 'ListLength')
]

# describes how each match order (in match_orders) should be handled
# sheet: this will be used to create different worksheets in output spreadsheet
#        there must be at most one order using this handling policy
# row:   this will be used as row header (vertical header in first column)
#        there must be at most one order using this handling policy
# col:   this will be used as column header (horizontal header in first row)
#        there must be at most one order using this handling policy
# at least one row or col should be specified
# empty string: all of them will be merged to create table titles;
# in case there are multiple sets of data, each set of data will be in a table
# and all tables will be vertically placed with one empty line
order_handling = ['sheet', '', 'col']

# each element in a list: (regex, key group name, key literal, value group name)
# regex should not be empty
# key can either be specified as group name, or a literal. the other should be empty
match_row = [
  (r'(?P<column>\w+): (?P<value>\d+\.\d+)', 'column', '', 'value')
]

# what lines to skip
skip_literal_list = []
skip_regex_list = [
  r'IFP GT Max Num Objects: \d+'
]

assert len(match_orders) == len(order_handling)

class DataCollector:
  def __init__(self):
    # each sheet is represented as a list of tables
    # each table is represented as a dict of:
    #   title: string; used to differentiate tables
    #   rows:  a list of string listing all known row headers
    #          (vertical header in first column)
    #   cols:  a list of string listing all known column headers
    #          (horizontal header in first row)
    #   data: a dict of dict of values; data[row][col] == value
    self.sheetDict = dict()
    self.defaultSheet = []
  
  def handleAddData(sheet, titleName, columnName, rowName, value):
    isCreateNewTable = True
    # if we are filling a missing spot from the last table, then we fill
    # the value in. If the value is already there, we create a new table
    if len(sheet) > 0:
      lastTable = sheet[-1]
      title = lastTable['title']
      rows = lastTable['rows']
      cols = lastTable['cols']
      data = lastTable['data']
      if titleName == title:
        # same table -- at least no contradiction yet
        isFillMade = False
        if rowName not in rows:
          isFillMade = True
          rows.append(rowName)
          data[rowName] = dict()
          if columnName not in cols:
            cols.append(columnName)
          data[rowName][columnName] = value
        elif columnName not in cols:
          isFillMade = True
          cols.append(columnName)
          data[rowName][columnName] = value
        elif columnName not in data[rowName]:
          isFillMade = True
          data[rowName][columnName] = value
        if isFillMade:
          isCreateNewTable = False
    if isCreateNewTable:
      newTable = {
        'title' : titleName,
        'rows' : [rowName],
        'cols' : [columnName],
        'data' : {rowName: {columnName: value}}
      }
      sheet.append(newTable)
  
  def addData(self, hierarchyDataList, key, value):
    assert type(hierarchyDataList) is list
    assert len(hierarchyDataList) == len(match_orders)
    assert type(key) is str
    assert type(value) is str
    columnName = key
    rowName = key
    dupHierarchy = []
    sheet = self.defaultSheet
    for i in range(len(hierarchyDataList)):
      h = hierarchyDataList[i]
      p = order_handling[i]
      if p == 'sheet':
        if h not in self.sheetDict:
          self.sheetDict[h] = []
        sheet = self.sheetDict[h]
      elif p == 'row':
        rowName = h
      elif p == 'col':
        columnName = h
      else:
        dupHierarchy.append(h)
    titleName = ''
    if len(dupHierarchy) == 1:
      titleName = dupHierarchy[0]
    else:
      titleName = ','.join(dupHierarchy)
    DataCollector.handleAddData(sheet, titleName, columnName, rowName, value)
  
  def processCellData(string):
    # if the string is an integer or floating point number,
    # convert them to the most appropriate type
    # test pure integer first
    stripped = string.strip()
    intBase = stripped
    if stripped.startswith('-'):
      intBase = stripped[1:]
    if intBase.isdigit():
      return int(stripped)
    
    # now test floating point numbers
    try:
      return float(stripped)
    except ValueError:
      # do nothing
      pass
    
    return stripped
  
  def writeSheet(sheetData, sheetOutput):
    curRowBase = 0
    for table in sheetData:
      title = table['title']
      rows = table['rows']
      cols = table['cols']
      data = table['data']
      sheetOutput.write(curRowBase, 0, DataCollector.processCellData(title))
      for c in range(len(cols)):
        sheetOutput.write(curRowBase, 1 + c, DataCollector.processCellData(cols[c]))
      for r in range(len(rows)):
        rowIndex = curRowBase + 1 + r
        sheetOutput.write(rowIndex, 0, DataCollector.processCellData(rows[r]))
        rowData = data[rows[r]]
        for c in range(len(cols)):
          key = cols[c]
          if key in rowData:
            sheetOutput.write(rowIndex, 1 + c, DataCollector.processCellData(rowData[key]))
      curRowBase += 2 + len(rows)
      
  
  def write(self, outputName):
    workbook = xlsxwriter.Workbook(outputName)
    if 'sheet' in order_handling:
      assert len(self.defaultSheet) == 0
      for sheetName, sheetData in self.sheetDict.items():
        sheetOutput = workbook.add_worksheet(sheetName)
        DataCollector.writeSheet(sheetData, sheetOutput)
    else:
      assert len(self.sheetDict) == 0
      sheetOutput = workbook.add_worksheet()
      DataCollector.writeSheet(self.defaultSheet, sheetOutput)
    workbook.close()

def processLog(logFileName, outputName):
  collector = DataCollector()
  hierarchyData = [None] * len(match_orders)
  isHavingData = False
  with open(logFileName, 'r') as f:
    lc = 1
    line = f.readline()
    while line:
      strippedline = line.strip()
      isMatched = False
      # check if we know this is something we should skip
      for g in skip_literal_list:
        if strippedline == g:
          isMatched = True
          break
      if isMatched:
        line = f.readline()
        lc += 1
        continue
      for g in skip_regex_list:
        if re.match(g, strippedline):
          isMatched = True
          break
      if isMatched:
        line = f.readline()
        lc += 1
        continue
      for i in range(len(match_orders)):
        regex, name = match_orders[i]
        if len(regex) == 0:
          # this is a series
          dict_series = match_series_dict[name]
          for header, seriesName in dict_series.items():
            if strippedline == header:
              isMatched = True
              hierarchyData[i] = seriesName
              break
        else:
          # this is a header with info that needs regex extraction
          result = re.match(regex, strippedline)
          if result:
            isMatched = True
            hierarchyData[i] = result.group(name)
            break
        if isMatched:
          break;
      if not isMatched:
        # we are not changing hierarchy position
        for t in match_row:
          regex, keyGroup, keyLiteral, valueGroup = t
          result = re.match(regex, strippedline)
          if result:
            isMatched = True
            key = keyLiteral
            if len(keyGroup) > 0:
              key = result.group(keyGroup)
            value = result.group(valueGroup)
            collector.addData(hierarchyData, key, value)
            isHavingData = True
            break
        if not isMatched:
          # we have an unrecognized line
          print('line {0} skipped: {1}'.format(str(lc), strippedline))
      line = f.readline()
      lc += 1
  
  if not isHavingData:
    return
  
  collector.write(outputName)

if __name__ == "__main__":
  logFileName = 'log.txt'
  outputName = 'result.xlsx'
  if (len(sys.argv) > 1):
    logFileName = sys.argv[1]
  if (len(sys.argv) > 2):
    outputName = sys.argv[2]
  processLog(logFileName, outputName)


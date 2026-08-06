import urllib.parse
from bs4 import BeautifulSoup
html = """
<select id="modalEmpSelect">
    <optgroup label="Bolim-1">
        <option value="1" data-dept-id="10">User 1</option>
        <option value="2" data-dept-id="10">User 2</option>
    </optgroup>
    <optgroup label="Bolim-2">
        <option value="3" data-dept-id="20">User 3</option>
    </optgroup>
</select>
"""
soup = BeautifulSoup(html, 'html.parser')
select = soup.find('select')
for child in select.children:
    if child.name == 'optgroup':
        print(child['label'])
        for opt in child.find_all('option'):
            print('  ', opt['value'], opt['data-dept-id'])

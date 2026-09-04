import re

with open('raw_dump.txt', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
cleaned_lines = []
for l in lines:
    match = re.match(r"^\d+: (.*)$", l)
    if match:
        cleaned_lines.append(match.group(1))

with open('src/pages/Analysis.jsx', 'w', encoding='utf-8') as out:
    out.write('\n'.join(cleaned_lines))
print("Restored successfully!")

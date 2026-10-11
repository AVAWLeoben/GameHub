"""Optional one-time integration of WasteKart into the classic GameHub menu.

Run at the repository root: python add_wastekart_to_gamehub.py
Safely refuses to modify unknown main.py layouts; makes a backup first.
"""
from pathlib import Path
import ast
import re
import shutil
import sys


def integrate(filename):
    path=Path(filename)
    if not path.exists():
        raise RuntimeError(f'Not found: {path}')
    src=path.read_text(encoding='utf8')
    if 'import wasteKart' in src or 'wasteKart.main' in src:
        print('WasteKart already appears registered; no changes made.')
        return False
    tree=ast.parse(src)
    games=None; buttons=None; game_menu=None
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id=='GAMES' and isinstance(node.value,ast.List):
                    games=node.value
        if isinstance(node,ast.AsyncFunctionDef) and node.name=='game_menu':
            game_menu=node
            for statement in node.body:
                if isinstance(statement,ast.Assign):
                    if any(isinstance(t,ast.Name) and t.id=='buttons' for t in statement.targets):
                        if isinstance(statement.value,ast.List):buttons=statement.value
    if games is None or buttons is None or game_menu is None:
        raise RuntimeError('GameHub main.py uses a different menu layout. See README for manual integration.')
    callbacks=[int(match) for match in re.findall(r'^def but(\d+)\(',src,re.M)]
    callback_number=max(callbacks,default=0)+1
    nbuttons=len(buttons.elts)
    # Classic GameHub has 5 columns, starting x=50/y=200.
    x=50+150*(nbuttons%5)
    y=200+200*(nbuttons//5)
    lines=src.splitlines(keepends=True)
    newline='\r\n' if '\r\n' in src else '\n'
    # Append commas to the previous final items. The legacy GameHub GAMES
    # list ends without a comma; otherwise the following tuple becomes a
    # function-call expression and crashes when the launcher imports main.py.
    for node in (games,buttons):
        if node.elts:
            last_line=node.elts[-1].end_lineno-1
            original=lines[last_line]
            if not original.rstrip().endswith(','):
                lines[last_line]=original.rstrip('\r\n')+','+newline
    additions={}
    def add(before_line,string):
        additions.setdefault(before_line,[]).append(string)
    # The list node closing bracket is on end_lineno, insert immediately above it.
    add(games.end_lineno,f'    ("WasteKart", wasteKart.main),{newline}')
    add(buttons.end_lineno,f'        Button({x}, {y}, 100, 100, "assets/WasteKart/kart_icon.png", "assets/WasteKart/kart_icon.png", but{callback_number}),{newline}')
    add(game_menu.lineno, f'def but{callback_number}():{newline}    global selected_game_func{newline}    selected_game_func = wasteKart.main{newline}{newline}{newline}')
    # Add import adjacent to other game imports but without rearranging them.
    import_lines=[n.end_lineno for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
    if not import_lines:
        raise RuntimeError('Cannot identify Python imports in main.py')
    add(max(import_lines)+1,f'import wasteKart{newline}')
    new=''.join(''.join(additions.get(i,[]))+line for i,line in enumerate(lines,1))
    new+=''.join(additions.get(len(lines)+1,[]))
    ast.parse(new)
    backup=path.with_name(path.name+'.before_wastekart.bak')
    if backup.exists():
        raise RuntimeError(f'A backup already exists: {backup}; refusing to overwrite.')
    shutil.copy2(path,backup)
    path.write_text(new,encoding='utf8')
    print(f'Added WasteKart to {path}; saved original as {backup}.')
    return True


if __name__=='__main__':
    target=Path('WasteGame/main.py')
    if not target.exists() and Path('main.py').exists():
        target=Path('main.py')
    try:integrate(target)
    except Exception as exc:
        print(f'Integration not applied: {exc}',file=sys.stderr)
        sys.exit(1)

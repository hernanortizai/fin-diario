p = "generar_arq.py"
s = open(p, encoding="utf-8").read()
s = s.replace('    ("Architizer", "https://architizer.com/blog/feed/"),\n', '')
s = s.replace("Dezeen, ArchDaily, Designboom, Architizer", "Dezeen, ArchDaily, Designboom")
open(p, "w", encoding="utf-8").write(s)
print("listo")

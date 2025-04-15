with open('words.txt', 'r') as f: words = set(word.strip().lower() for word in f.readlines())
with open('starters.txt','w') as f:
    dic = {
        i-1: [word[:i-1] for word in words if len(word[:i-1]) > 0] for i in range(1, 8) }
    f.write(str(dic))
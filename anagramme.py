import json
from collections import defaultdict

class AnagrammeFinder:
  def __init__(self, filename):
    self.fullDict = dict()
    with open(filename) as file:
      self.fulldict = json.loads(file.read())

  def find(self, tosearch):
    self.tosearch = tosearch
    self.tosearchChar = self.getCharDict(self.tosearch)
    firstPass = dict()
    for key, value in self.fulldict.items():
      if self.tosearchChar.keys() >= value.keys():
        if all(self.tosearchChar[char] >= value[char] for char in value):
          firstPass[key] = value

    Q = len(tosearch)
    firstPassWords = firstPass.keys()

    bag = defaultdict(list)
    bag[0].append(tuple())
    count = 0
    for card in firstPassWords:
      for size in range(Q-1,-1,-1):
        if size + len(card) <= Q and size in bag:
          # Detect too many char
          if len(bag[size])>10000:
            raise BufferError("Anagramme too large")
          for combinaison in bag[size]:
            count+=1
            combinaison = combinaison + (card,)
            if self.correctCombi(combinaison):
              bag[size+len(card)].append(combinaison)
    print(count)
    return bag[Q]
  
  def getCharDict(self, word):
    tmpdict = defaultdict(int)
    for char in word:
      tmpdict[char] += 1
    return tmpdict

  def correctCombi(self, combinaison):
    currentChar = self.tosearchChar.copy()
    for word in combinaison:
      for char,number in self.fulldict[word].items():
        if currentChar[char] >= number:
          currentChar[char] -= number
        else:
          return False
    return True

# import cProfile
# prof = cProfile.Profile()
# prof.enable()
# APIanagramme = AnagrammeFinder("anagramme.txt")
# print(APIanagramme.find("TESTPERFORMANCE"))
# prof.disable()
# prof.print_stats()
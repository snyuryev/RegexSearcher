#!/usr/bin/python
#
# Demonstration of simple search using regex as the "engine".

import re

SEARCH_FILE_NAME  = "searchtest.txt"   # File containing the text we'll search against
QUERY_FILE_NAME   = "queries.txt"      # File containing the queries to run, one per line
SYNONYM_FILE_NAME = "synonyms.txt"     # File containing synonyms, one set per line, individuals separated by pipes
MATCH_WINDOW     = 500    # How many characters (x2) will we look within for a match?  This is our "AND" character distance
PRECEDING_CHARS  =  20    # How many characters before a match to show in the KWIC text?
FOLLOWING_CHARS  =  30    # How many characters after the end of a match to show in the KWIC text?
MAX_KWIC_CHARS   = 100    # How much maximim KWIC (KeyWord In Context) text?
MAX_HITS         =   8    # How many hits to limit to?

# --------------------------------------------------------------------------------------------------------------------

class Token:
    """
    Token represents an individual "term" extracted from the input query.  A Token may also be a literal string (a clause)
    as defined by double-quotes.
    """

    def __init__ (self):

        self.token        = ""      # Records the string that makes up this token
        self.isLiteral    = False   # Is this token to be literally (exactly) searched?
        self.startSpecial = None    # Did it start specially?  (For us, just double-quote.)
        self.endSpecial   = None    # Did it end specially?  (For us, just double-quote.)

    def __str__ ( self ):
        """
        Return a print-happy string representation of ourselves ...
        """
        return "%s%s%s%s" % (
            ("", "<LITERAL>")[self.isLiteral],
            ("", "[%s]" % self.startSpecial)[self.startSpecial is not None],
            self.token,
            ("", "[%s]" % self.endSpecial)[self.endSpecial is not None]
            )

    def finalizeExtraction ( self, inLiteral ):
        """
        We're going to do some simple clean-up, here.  But if we're already in a literal string, just check
        to see if we complete it ...

        If we started or ended with a special character, record it.

        1. If the token starts with a parenthesis:
            a.  If it ends with a parenthesis, keep the parens:  (a)(2)
            b.  Otherwise, remove the parens.
        2. If the token ends with a parenthesis:
            a.  If there is a start-paren in the word, keep the parens:  168(a)
            b.  Otherwise, remove the parens.
        3. If the token starts with a double-quote:
            a.  If it ends with a double-quote, remove the quotes, mark as literal, and stop further processing:  "sec.(192)"
            b.  Otherwise, remove the double-quote and store it as a starting special character.
        4. If the token ends with a double-quote, and we haven't already picked it up, remove it.
        5. If the token starts with a period, colon or single-quote, remove.
        6. If the token ends with a period, colon or single-quote, remove.

        If the token is an uppercase OR or AND, assume that the user is trying to use boolean, and throw
        out the entire token (as the search will default to AND, anyhow).
        """

        if inLiteral:
            self.isLiteral = True
            if self.token[len(self.token)-1] == '"':  # Then we're the end of a literal string
                self.endSpecial = '"'
                self.token = self.token[0:len(self.token)-1]  # Trim off the double-quote
        else:

            removeStartOrEndChars = "'.:"

            startChar = 0
            isStillProcessing = True

            # Trim the front of the word ...
            while isStillProcessing and startChar < len(self.token) :

                if self.token[startChar] == "(":
                    if self.token[len(self.token)-1] == ")":
                        # Stop processing, and keep the rest of the word
                        isStillProcessing = False
                    else:
                        self.token = self.token[1:]  # Trim off the first character and keep going ...
                        startChar -= 1  # Account for our missing character ...
                elif self.token[startChar] == '"':
                    if self.token[len(self.token)-1] == '"':
                        self.isLiteral = True
                        self.startSpecial = '"'
                        self.endSpecial = '"'
                        self.token = self.token[1:len(self.token)-1]  # Trim off first and last characters and keep going ...
                    else:
                        self.startSpecial = '"'
                        self.isLiteral = True
                        # Trim off the starting character ...
                        self.token = self.token[1:]
                        startChar -= 1
                        # Assume the rest of the whole word is literal ...
                        isStillProcessing = False
                elif removeStartOrEndChars.find( self.token[startChar] ) != -1:
                    # Then just remove it ...
                    self.token = self.token[1:]  # Trim it off
                    startChar -= 1  # Account for our missing character ...
                else:
                    isStillProcessing = False
                startChar += 1

            # Trim the end of the word ...
            isStillProcessing = True
            endChar = len(self.token) - 1
            while isStillProcessing and not self.isLiteral and endChar >= 0:

                if self.token[endChar] == ")":
                    if self.token.find("(") != -1:  # Then there's an open-parens in the word.  Keep it all.
                        isStillProcessing = False
                    else:
                        self.token = self.token[0:endChar]
                elif self.token[endChar] == '"' or removeStartOrEndChars.find( self.token[endChar] ) != -1:
                    # Since we're not currently in a literal, this is just junk.  Remove it.
                    self.token = self.token[0:endChar]
                else:
                    isStillProcessing = False
                endChar -= 1

            # If the user is trying to force a boolean search, rather than mysteriously failing for them
            # (which it probably would do), just erase the token -- it'll search AND by default, anyhow ...
            if self.token == "AND":
                self.token = ""
            if self.token == "OR":
                self.token = ""

# --------------------------------------------------------------------------------------------------------------------

class ParseList:
    """
    Properly, this would be a ParseTree, as you really want to be working with operators and operands,
    but as we're doing this really simply, it's just a list of the tokens.
    """

    def __init__ ( self ) :
        self.tokens = []

    def __str__ ( self ) :
        """
        Collate our tokens for printing ...
        """
        output = ""
        for token in self.tokens:
            output = output + str(token) + "\n"
        return output

# --------------------------------------------------------------------------------------------------------------------

class Tokenizer:
    """
    The Tokenizer is used to break up an input query into a ParseList (properly, would break it up into a
    ParseTree).  For a more proper implementation, see Aho, Sethi & Ullman.
    """

    spaces = " ,;\n\r\t"

    def __init__ ( self ):
        pass

    def tokenize ( self, searchExpression ):
        """
        This is a stupidly simple (and easily optimized on almost any platform) tokenizer.  You could probably do
        this better with a regex, but kept this for straightforwardness.  Of course, the *right* way to do this is
        to write an actual, simple state tokenizer.  For all such things, see Aho, Sethi & Ullman.

        Essentially, we scan through the string, starting a new token any time we find non-space characters.  We
        keep track of whether or not we're between double-quotes to handle literal searches.
        """

        parseList = ParseList()   # New list for us to add tokens to
        currToken = None          # No token started yet ...
        inLiteral = False         # No double-quote seen yet ...

        for char in searchExpression:

            if self.spaces.find(char) != -1:   # Then it's space character ...
                if currToken is not None:  # We need to close out the prior word ...
                    currToken.finalizeExtraction(inLiteral)
                    if currToken.isLiteral:
                        if currToken.endSpecial == '"':  # Then we closed out a literal string ...
                            inLiteral = False
                        else:
                            inLiteral = True
                    else:
                        inLiteral = False
                    if len(currToken.token) > 0:  # Ensure we have something ... might have also nuked the word in finalization.
                        parseList.tokens.append(currToken)
                    currToken = None
                else:
                    # Keep going and just eat the character ...
                    pass
            elif currToken is not None:        # Then we're in the midst of a word ...
                currToken.token = currToken.token + char
            else:                              # It's not a space, and we're not in a word yet ...
                # We're starting a new word ...
                currToken = Token()
                currToken.token = char

        if currToken is not None:  # Then we need to close out the prior word
            currToken.finalizeExtraction(inLiteral)
            if len(currToken.token) > 0:  # Ensure we have something ... might have also nuked the word in finalization.
                parseList.tokens.append(currToken)

        return parseList

class SearchMatcher:
    """
    Little helper class to store a regular expression and a matcher for searching ease.
    """

    def __init__ (self, regex, matcher):
        self.regex = regex
        self.matcher = matcher

# --------------------------------------------------------------------------------------------------------------------

class HitPosition:
    """
    Little helper class to start start and end of a match.
    """
    def __init__(self, start, end):
        self.start = start  # First part of hit
        self.end   = end    # Last part of hit

# --------------------------------------------------------------------------------------------------------------------

class Lemmatizer:
    """
    Let's just do some stupid lemma handling for grins.  This is just to show how you could extend
    this fairly easily to handle some common cases.
    """

    def __init__ (self):
        pass

    def expandEquivalencies ( self, term ):
        """
        We're just going to handle some very simple cases ...
        horses --> horse[s]*
        horse --> horse[s]*

        This has nothing to do with lemmatization, but because in theory we could be splitting up the term, here
        (properly, all of that should go into a parse tree ...), we're going to add equivalencies for S/section symbol
        and P/paragraph symbol at the start of words.
        """

        if len(term) < 2:
            return term

        if term[0] == "s" and term[1].isdigit():
            term = "(s|\u00a7)" + term[1:]   # If it was an S in front of a number, also match the section symbol
        if term[0] == "p" and term[1].isdigit():
            term = "(p|\u00b6)" + term[1:]   # If it was a P in front of a number, also match the paragraph symbol

        # This is a poor English-only pluralization handler.  You should at least throw in a couple other cases (such as "business/businesses"),
        # and definitely think about what can be done for French, Dutch, German and Polish.
        if term[len(term)-1] == "s":
            return term[0:len(term)-1] + "[s]*"
        if term[len(term)-1].isalpha():
            return term + "[s]*"
        return term

# --------------------------------------------------------------------------------------------------------------------

class Synonyms:
    """
    Let's just do some fairly stupid synonym expansion for grins.  This is just to show how you could extend
    this fairly easily to handle common cases.

    NOTE:  Because we do synonyms before we do lemma expansion, you MUST include all variants in the list
    in order to get good matches.  This is cheap and sleazy.  You should fix this processing!

    Also, be sure to put things in the list in the form that they'll match tokenized terms.  E.g., remove the trailing period.
    """

    def __init__ ( self ) :
        """
        Load up from an equivalencies file with each equivalency separated by a pipe.
        """
        self.dictionary = { }
        f = open(SYNONYM_FILE_NAME, "r")
        equivalencies = f.read().splitlines()
        for equivalency in equivalencies:
            # Each synonym on the line is separated by a pipe
            synonymList = equivalency.split("|")
            # Throw them in a dictionary for easier retrieval ...
            for synonym in synonymList:
                self.dictionary[synonym] = synonymList

    def expandTerm ( self, term ):
        """
        Return either the term, or a list of terms.
        """
        if term in self.dictionary:
            return self.dictionary[term]
        else:
            return [ term ]

# --------------------------------------------------------------------------------------------------------------------

class SearchExecution:
    """
    The SearchExecution class takes a ParseList (or properly, a ParseTree) and executes the search, generating
    a SearchResult

    Note that because we're working with a very simplified structure (i.e., a ParseList rather than a proper
    ParseTree), we are just doing our Analysis() step in place here (e.g., lemmatization, synonyms, etc.).
    Properly, that should be done in an earlier step on the ParseTree, and we'd walk the parse-tree in in-fix
    order here (but that's also very difficult when generating a regex).

    First, we create a list of all our AND clauses -- specifically, to merge together any literal
    strings of tokens.  Then we turn each one into a word-match regex.

    I tried just creating all the permutations, and stringing them together into a big OR clause ... but that
    turned out to really slow down with longer searches.  So, to speed it up, sort the list in order of the longest
    clause first (on the theory that it'll produce the least matches), and scan to find a match for it.  Then,
    establish a search perimeter (I just use character distance -- but if you had page markers, you might use them --
    and if your records are just pages, then maybe you don't even need a perimeter) and look for each of the other matches
    within that perimeter.

    """

    wordBoundaries = r'[ .,:;\n\r\t\(\)\[\]]'

    def __init__ (self ) :
        self.lemmatizer = Lemmatizer()
        self.synonyms   = Synonyms()


    def executeSearch (self, parseList, content, isVerbose ):

        searchResult = SearchResult(content)

        andClauses = []

        # First, collect all the tokens into "literal" strings (i.e., consolidate the literal clauses)
        currentClause = ""
        for token in parseList.tokens:
            if token.isLiteral:
                if len(currentClause) > 0:  # Then we're the second+ word in the clause ...
                    currentClause += " "
                currentClause += token.token
            else:
                if len(currentClause) > 0:   # Then we just walked off the end of a literal ...
                    andClauses.append(currentClause)  # Add the prior literal ...
                    currentClause = ""                # And "zero it out"
                andClauses.append(token.token) # Then store our word
            # Take care of any trailing literal ...
        if len(currentClause) > 0:
            andClauses.append(currentClause)

        # Sort the clauses into a "longest-first" order, to (presumably) search on the lowest matches first.
        # This is just Python syntax for a reverse length string sort on an array ...
        andClauses.sort(  lambda x, y: cmp(len(y), len(x)) )

        # Now, turn each one into a word-matching regex
        searchClauses = []
        for clause in andClauses:
            isFirst = True
            regex = ""
            for synonym in self.synonyms.expandTerm(clause.lower()):
                # Note that we escape the term BEFORE passing it to the lemmatizer, as the lemmatizer is going
                # to add regular expression markup to it.  Be careful when you do this, and what you expect to
                # happen afterwards.
                lemmatized = self.lemmatizer.expandEquivalencies( re.escape(synonym))
                if isFirst:
                    isFirst = False
                else:
                    regex += "|"
                regex += "(^|" + self.wordBoundaries + ")" + lemmatized + "($|" + self.wordBoundaries + ")"  # Escape it to capture any regex metacharacters in there (e.g., parens).
            if isVerbose:
                print regex
            searchClauses.append( SearchMatcher(regex, re.compile(regex, re.IGNORECASE|re.DOTALL)))  # Cache a copy of the regex, and a compiled matcher

        # Just test for an edge case ... if no search clauses, no search!
        if len(searchClauses) < 1 :
            return searchResult

        # Now, we look for decent AND matches.  We define an AND match as all the words co-occuring within some
        # given distance.  We arbitrarily select "about" 500 characters (could be more).  To do this, we:
        #   1. Regex match to find the first word
        #   2. Establish a bracket before and after the match we found
        #   3. Search for *all* the rest of the words within that zone, and for each one, take the match closest to
        #      the first word we found (for highlighting purposes).
        #   4. If we find all the words in that zone, record the closest ones, and save it as a search hit.

        scanStart = 0

        while scanStart < len(content.content) and len(searchResult.hits) < MAX_HITS:  # While we're not exhausted ...

            highlights = []

            match = searchClauses[0].matcher.search( content.content, scanStart )

            if match is None:   # Then we're done!
                break

            # OK, we found a match.
            # Save the highlight
            hitPosition = HitPosition(match.start(), match.end())
            # Trim the bits we matched before and after off the hit, as our regex includes the space characters.
            if hitPosition.start != 0:
                hitPosition.start += 1
            if hitPosition.end != len(content.content) - 1:
                hitPosition.end -= 1
            highlights.append(hitPosition)

            # Now see if the rest of our words are within the bracket.  If you had something
            # useful like page markers, you might want to limit by page boundaries, rather than a window.
            startBracket = match.start() - MATCH_WINDOW
            endBracket   = match.end()   + MATCH_WINDOW
            if startBracket < 0:
                startBracket = 0
            if startBracket < scanStart:  # Be sure we don't go back to a previous occurance ...
                startBracket = scanStart
            if endBracket >= len(content.content):  # And be sure we don't walk off the end of the content ...
                endBracket = len(content.content)

            skipFirst    = True
            failed       = False
            lastPosition = match.end()

            for clause in searchClauses:
                if skipFirst:  # Skip over the first one, we already did it.
                    skipFirst = False
                else:
                    nextStart   = startBracket
                    bestMatch   = None
                    minDistance = 999999

                    # Loop through matches until we find one that's closest to our first match word
                    while True:

                        otherMatch = clause.matcher.search( content.content, nextStart, endBracket )
                        if otherMatch is None:  # No more matches on this word ... quit
                            break
                        else:
                            # Find the distance between us and the original match.
                            if otherMatch.start() < match.start():  # Then distance is end to start
                                ourDistance = match.start() - otherMatch.end()
                            else:
                                ourDistance = otherMatch.start() - match.end()

                            if ourDistance < minDistance:  # First match makes it our best match, or our distance could be better
                                bestMatch = otherMatch
                                minDistance = ourDistance

                            nextStart = otherMatch.end() + 1

                    if bestMatch is None:   # Then we didn't find any matches ... failure!
                        failed = True
                        break   # Quit

                    # Save our hit ...
                    hitPosition = HitPosition(bestMatch.start(), bestMatch.end())
                    # Trim the bits we matched before and after off the hit, as our regex includes the space characters.
                    if hitPosition.start != 0:
                        hitPosition.start += 1
                    if hitPosition.end != len(content.content) - 1:
                        hitPosition.end -= 1

                    highlights.append(hitPosition)

                    # And check to see if we've extended the scan range from which to start our next scan ...
                    if bestMatch.end() > lastPosition:
                        lastPosition = bestMatch.end()

            # OK.  By the time we get here, we either failed, or we found all our terms.
            if failed:  # Well, no matches!  Quit.
                break

            # So, we now have highlights for all our matched words.  Let's record the hit, and start our
            # next scan following our last location.

            # First, sort the hits into match order, for simplicity in calculating the KWIC text ...
            # Again, this is just funky Python syntax for sorting a list of matches in order of match start ...
            highlights.sort( lambda x, y: cmp(x.start, y.start))

            searchResult.hits.append( highlights )
            scanStart = lastPosition + 1  # Move past our current match to keep going ...

        return searchResult

# --------------------------------------------------------------------------------------------------------------------

class SearchResult:
    """
    The results of a search.  Each hit consists of a set of HitPositions indicating the word hits.  We use
    that for highlighting.

    It's a little sleazy, but we store a reference to the content we searched to simplify the syntax for
    printing out the results (so we can just directly fetch the KWIC text) ...
    """

    def __init__ (self, content ):
        self.hits = []   # Our hits keywords in context ...
        self.content = content.content  # Just save the actual string.  Sleazy, I know ...

    def calculateKWIC ( self, hit ):
        """
        Given a hit (list of matches), calculate the KWIC (keyword in context) text for it ...
        """
        kwicText = ""

        startKWIC  = hit[0].start - PRECEDING_CHARS
        # Now move backwards until we find a space ...
        while startKWIC > 0 and self.content[startKWIC-1] != " ":
            startKWIC -= 1

        # OK, now move forward, building up the text, until we run out of matches, or we exceed
        # our maximum KWIC text length ...
        for highlight in hit:  # For each match in our list of matches ...

            start = highlight.start
            end   = highlight.end
            if start > startKWIC:
                kwicText += self.content[ startKWIC : start ]   # Add the text before our match
            kwicText += "<<"    # Start highlight
            kwicText += self.content[ start : end ]  # Add in the matched text
            kwicText += ">>"    # End highlight

            startKWIC = end

            if len(kwicText) > MAX_KWIC_CHARS:  # OK, too long ... no more highlights
                break

        # Now, take some text off the end ...
        endKWIC = startKWIC + FOLLOWING_CHARS

        # Really, we ought to not add additional end text if we've already exceeded our max length, but
        # it's getting close to dinner time ... so that's left as an exercise for the reader ... <g>

        while endKWIC < len(self.content) and self.content[endKWIC] != " ":
            endKWIC += 1

        kwicText += self.content[startKWIC:endKWIC]

        return kwicText


    def __str__ ( self ):
        """
        Produce a string for simple printing of results ...
        """
        output = ""
        for hit in self.hits:
            output += "\n---\n"
            output += self.calculateKWIC(hit)
        return output

# --------------------------------------------------------------------------------------------------------------------

class Content:
    """
    This is just what we're going to search against.  For testing purposes, we just read the SEARCH_FILE_NAME
    and run our search against that.
    """

    def __init__ (self):
        f = open(SEARCH_FILE_NAME, 'r')
        self.content = f.read()    # Load the contents of the file ...


# --------------------------------------------------------------------------------------------------------------------

def runSearch ( searchExpression, content, isVerbose ) :
    """
    Driver to run a search for a given expression and content.
    """

    if isVerbose:
        print "-->%s<--" % searchExpression
    tokenizer = Tokenizer()
    parseList = tokenizer.tokenize( searchExpression )
    if isVerbose:
        print parseList
    searchExecution = SearchExecution()
    searchResult = searchExecution.executeSearch(parseList, content, isVerbose)

    return searchResult

def testExpressions ( ):
    """
    Just some various test-cases to ensure that the overall parsing is working correctly.
    Of course, this should be a unit test . . !
    """
    f = open(QUERY_FILE_NAME, 'r')
    parseStrings = f.read().splitlines()

    content = Content()

    for test in parseStrings:
        print "\n======================================\n"
        searchResult = runSearch(test, content, True)
        print searchResult
        print "\n======================================\n"


# If we're just running this file, then run the test expressions.
if __name__ == '__main__':
    testExpressions()

# Phase 4A: factual and semantic evidence audit

Preparation date: 2026-10-25

These are research-assistant assessments for independent review, not reviewer decisions or approvals.
All 24 original questions, gold answers and proposals are preserved. The original package remains unchanged.
All human decisions remain pending; reviewer identity, review timestamp and approved target are blank.

## Assessment summary

```json
{
  "classification_counts": {
    "needs_revision": 5,
    "recommended_for_independent_review": 16,
    "reject": 3
  },
  "count": 24,
  "independently_approved_targets": 0,
  "limitation": "Offline validation verifies bindings and pending state, not factual correctness or authenticity of recorded source access.",
  "recommended_ids": [
    "p02",
    "p03",
    "p06",
    "p07",
    "p08",
    "p09",
    "p10",
    "p12",
    "p13",
    "p15",
    "p16",
    "p17",
    "p18",
    "p21",
    "p22",
    "p23"
  ],
  "replacement_proposals": 7,
  "schema": "answer-compatible-targets/evidence-audit-summary-v1",
  "source_access_counts": {
    "opened": 52,
    "search_excerpt_only": 3
  }
}
```

A recommendation means the evidence is suitable to put before an independent reviewer; it does not certify truth, entailment or experiment readiness.
Credits-based exclusions are identified as inferences. Search excerpts and failed opens are explicitly distinguished from opened page text.
Replacements are development-only leads, all unverified; they have not been substituted into the original package or execution pipeline.

## Findings for all 24 nominations

### p01: reject

Query ID: `5a7557d75542992d0ec05f68`

Which "Roseanne" star is in Scream 2?

Gold: **Laurie Metcalf**. Proposed target: **Rosie O'Donnell**.

**Correct-answer investigation:** Metcalf is supported by both Roseanne and Scream 2 credits.

**Candidate falsehood:** O’Donnell is absent from the checked Scream 2 list, but this alone is not exhaustive exclusion.

**Semantic compatibility:** Reject this nomination: generic television celebrity status does not establish the required Roseanne-star premise.

**Aliases and ambiguity:** Rosie/Roseann O’Donnell is not Laurie Metcalf; similar Roseann/Roseanne spelling is not a TV credit.

**Verification limits:** No qualifying O’Donnell Roseanne-star credit established. No defensible different Roseanne-star gold answer found in the verified development pool. Replace the question rather than invent a target.

Sources: [S01](https://www.televisionacademy.com/bios/laurie-metcalf), [S02](https://en.wikipedia.org/wiki/Rosie_O'Donnell), [S03](https://en.wikipedia.org/wiki/Scream_2).

**Unverified replacement lead** — query `5abc41315542993a06baf8bb`:

Mía Maestro had a role in the 2002 biopic directed by whom?

Gold: Julie Taymor; proposed target: Rob Reiner; development source: `5a87106555429960ec39b71f`.

Use the development Frida-director question with Rob Reiner, another film director.

Limits: Miramax supports Taymor/Maestro but has erroneous release metadata; verify the 2002 date and Reiner-specific exclusion before submission.

### p02: recommended_for_independent_review

Query ID: `5a72f1cf5542994cef4bc414`

Which English actor starred in the 1995 american romantic drama film The Scarlet Letter alongside Demi Moore and Robert Duvall?

Gold: **Gary Oldman**. Proposed target: **Chiwetel Ejiofor**.

**Correct-answer investigation:** Disney’s archive directly supports Oldman, the 1995 date and the Moore/Duvall co-stars.

**Candidate falsehood:** Ejiofor is not in the expanded credited cast; this is a documented credits-based falsehood inference.

**Semantic compatibility:** Compatible English male film actor; substituting a cast member is coherent.

**Aliases and ambiguity:** Gary Oldman and Chiwetel Ejiofor are distinct people. Other English supporting actors make the gold nonexclusive, but do not make Ejiofor correct.

**Verification limits:** Independent reviewer must check complete credits/uncredited appearances; London birth supports the English qualifier without conflating citizenship.

Sources: [S04](https://d23.com/a-to-z/scarlet-letter-the-film/), [S05](https://en.wikipedia.org/wiki/The_Scarlet_Letter_(1995_film)), [S06](https://en.wikipedia.org/wiki/Chiwetel_Ejiofor).

### p03: recommended_for_independent_review

Query ID: `5ae2c416554299492dc91c67`

Which American actor portray Steve Urkel in "Family Matters"

Gold: **Jaleel Ahmad White**. Proposed target: **Ben Savage**.

**Correct-answer investigation:** Broadcaster biography identifies White as Steve Urkel.

**Candidate falsehood:** Ben Savage is a different actor associated with Cory Matthews, not the credited Urkel performer.

**Semantic compatibility:** Strongly matched US male sitcom actor and a specific character-performance relation.

**Aliases and ambiguity:** Jaleel White and Jaleel Ahmad White are the same gold identity; Ben Savage is not that alias.

**Verification limits:** Review any alternate/guest portrayal claim against episode credits; the primary role attribution is positive evidence.

Sources: [S07](https://www.paramountpressexpress.com/cbs-media-ventures/shows/flip-side/talent/?view=jaleel-white-2), [S08](https://en.wikipedia.org/wiki/Ben_Savage).

### p04: needs_revision

Query ID: `5ae7f56e5542993210983fd1`

Who is the author of the series in which Rupert Grint plays one of the three main characters?

Gold: **J. K. Rowling**. Proposed target: **Jane Mayer**.

**Correct-answer investigation:** Grint resolves to Ron Weasley/Harry Potter; Rowling’s official biography supports authorship.

**Candidate falsehood:** Mayer is not the attributed Harry Potter author; author attribution supports exclusion, not a universal bibliography audit.

**Semantic compatibility:** Writer alone is too coarse: Mayer’s established nonfiction/journalism profile is a weaker genre match than a youth fantasy novelist.

**Aliases and ambiguity:** J.K./Joanne Rowling is not Jane Mayer. Film-series involvement must not be confused with authorship of the underlying books.

**Verification limits:** Replace the weak contextual target and independently check the replacement; do not modify the frozen question.

Sources: [S09](https://www.jkrowling.com/wp-content/uploads/2025/03/J.K.-Rowling-Biography-2025.pdf), [S10](https://en.wikipedia.org/wiki/Rupert_Grint), [S11](https://www.amacad.org/person/jane-m-mayer), [S53](https://madeleinelengle.com/).

**Unverified replacement lead** — query `5ae7f56e5542993210983fd1`:

Who is the author of the series in which Rupert Grint plays one of the three main characters?

Gold: J. K. Rowling; proposed target: Madeleine L'Engle; development source: `5ab870ee5542990e739ec8f6`.

Madeleine L’Engle is a development-sourced youth science-fantasy author and a closer genre match.

Limits: Official estate establishes A Wrinkle in Time background; replacement remains unapproved and requires independent Harry Potter exclusion.

### p05: reject

Query ID: `5a89bbb05542992e4fca83a3`

What star of Parks and Recreation appeared in November?

Gold: **Nick Offerman**. Proposed target: **Christopher Rich**.

**Correct-answer investigation:** Offerman is supported as Ron Swanson and Officer Roberts in November (2004).

**Candidate falsehood:** Rich is absent from the checked November list, but incomplete credit evidence is not universal proof.

**Semantic compatibility:** Reject: Rich’s Reba/Murphy Brown background does not establish that he is a Parks and Recreation star.

**Aliases and ambiguity:** Resolve Christopher Rich to actor Christopher Rich Wilson, not the theatre manager. November is the 2004/2005 film, not the calendar month.

**Verification limits:** No compatible different Parks and Recreation star found among development gold answers. The same unsupported show-membership issue as p01 remains.

Sources: [S12](https://www.televisionacademy.com/bios/nick-offerman), [S13](https://en.wikipedia.org/wiki/November_(2004_film)), [S14](https://en.wikipedia.org/wiki/Christopher_Rich_(actor)).

**Unverified replacement lead** — query `5ab97d0a5542996be202051e`:

Who was hung for assisting the attempted surrender of a defector from the American Continental Army to the British Army?

Gold: John André; proposed target: Marquis de Lafayette; development source: `5abf1ad15542997ec76fd3c2`.

Use the development John André execution question with Marquis de Lafayette: both are eighteenth-century military figures.

Limits: This is a proposed new question/target only. Verify André’s execution and Lafayette’s distinct biography and suitability; no external replacement evidence was checked here.

### p06: recommended_for_independent_review

Query ID: `5a83411655429966c78a6b5d`

Who created the NBC sitcom that Johnny Pemberton appears in as the character Bo Thompson?

Gold: **Justin Spitzer**. Proposed target: **Robert Ian "Rob" Sitch**.

**Correct-answer investigation:** Performer biography links Pemberton/Bo to Superstore; Spitzer’s speaker biography explicitly attributes creation.

**Candidate falsehood:** The named creator is Spitzer rather than the distinct Rob Sitch.

**Semantic compatibility:** Sitch is a television comedy writer/producer; this is a coherent creator substitution, unlike a random actor.

**Aliases and ambiguity:** Rob Sitch and Robert Ian Sitch are the same candidate; Justin Spitzer is not an alias.

**Verification limits:** Verify creator versus developer/executive-producer credit. Promotional biographies are primary statements about careers, not comprehensive credit registries.

Sources: [S15](https://banffmediafestival.playbackonline.ca/2022/speakers/968857/justinspitzer/), [S16](https://www.bluenotejazz.com/hawaii/tm-event/johnny-pemberton/), [S17](https://en.wikipedia.org/wiki/Rob_Sitch).

### p07: recommended_for_independent_review

Query ID: `5a72688c5542997f827839b2`

The Atik Valide Mosque and Valens Aqueduct are found in what country?

Gold: **Turkey**. Proposed target: **Netherlands**.

**Correct-answer investigation:** Both landmarks resolve to Istanbul, in modern Turkey.

**Candidate falsehood:** Netherlands is a distinct country and not the checked location of either named landmark.

**Semantic compatibility:** Country-to-country substitution preserves geographic granularity; local architectural plausibility remains a reviewer judgment.

**Aliases and ambiguity:** Turkey/Türkiye and Istanbul/Constantinople naming changes do not make Netherlands an equivalent answer.

**Verification limits:** Use modern location, not the nationality of ancient builders. Mosque location is government-backed; the aqueduct corroboration is secondary.

Sources: [S18](https://www.kulturportali.gov.tr/turkiye/istanbul/gezilecekyer/atik-valide-camii), [S19](https://en.wikipedia.org/wiki/Valens_Aqueduct).

### p08: recommended_for_independent_review

Query ID: `5a7796e05542992a6e59df0f`

What country is the theme park served by the Huis Ten Bosch train service themed on?

Gold: **Netherlands**. Proposed target: **Turkey**.

**Correct-answer investigation:** The named train reaches Huis Ten Bosch, whose park theme is Dutch/Netherlands.

**Candidate falsehood:** Turkey conflicts with the checked Netherlands theme.

**Semantic compatibility:** Both candidates are countries; the question asks theme, not the Japanese physical location.

**Aliases and ambiguity:** Netherlands/Dutch/Holland contextual labels do not alias Turkey.

**Verification limits:** Train route is operator-backed; park theme currently uses secondary evidence because the official visitor page returned 503.

Sources: [S20](https://www.jrkyushu.co.jp/english/train/htb.html), [S21](https://en.wikipedia.org/wiki/Huis_Ten_Bosch_(theme_park)).

### p09: recommended_for_independent_review

Query ID: `5a8242c155429940e5e1a81d`

Where was the author of Thoughts of Machiavelli born?

Gold: **Germany**. Proposed target: **Canada**.

**Correct-answer investigation:** The scholarly entry identifies Strauss, the book and Kirchhain, Germany.

**Candidate falsehood:** Canada is not Strauss’s checked birthplace country.

**Semantic compatibility:** Country answer matches the gold granularity; false birthplace assertion is coherent.

**Aliases and ambiguity:** Thoughts of is a typo for Thoughts on Machiavelli. Kirchhain was in the German Empire/Prussia; Germany is the conventional country rendering, not Canada.

**Verification limits:** Where could also accept a town name. Do not conflate birthplace, nationality and later US residence or change the frozen title text.

Sources: [S22](https://plato.stanford.edu/entries/strauss-leo/).

### p10: recommended_for_independent_review

Query ID: `5ac0fd56554299012d1db679`

Carrie Coon plays Margo Dunne in a 2014 film set in what state?

Gold: **Missouri**. Proposed target: **Pennsylvania**.

**Correct-answer investigation:** Studio confirms the 2014 film and Coon; secondary cast/plot support Margo and the main Missouri setting.

**Candidate falsehood:** Pennsylvania is not the checked principal state setting.

**Semantic compatibility:** US-state-to-US-state substitution preserves the requested type.

**Aliases and ambiguity:** Margo/Go Dunne are the same character. Missouri/MO and Pennsylvania/PA are not aliases.

**Verification limits:** Distinguish principal story setting from New York backstory and filming sites. Secondary setting/cast facts should be independently corroborated.

Sources: [S23](https://www.20thcenturystudios.com/movies/gone-girl), [S24](https://en.wikipedia.org/wiki/Gone_Girl_(film)).

### p11: needs_revision

Query ID: `5a8d12ca5542994ba4e3dbe2`

In what city is the company that Fastjet Tanzania was originally founded as a part of prior to rebranding based?

Gold: **Nairobi, Kenya**. Proposed target: **Rome**.

**Correct-answer investigation:** The intended chain is Fly540 Tanzania → Kenyan Fly540 → Nairobi.

**Candidate falsehood:** Rome conflicts with the checked historical Kenyan headquarters, conditional on that intended parent interpretation.

**Semantic compatibility:** City-to-city is coherent, but the corporate referent and time period must be resolved before recommending the pair.

**Aliases and ambiguity:** Fly540/Five Forty Aviation are linked names; Fly540 Tanzania and later Fastjet parent companies are separate entities. Nairobi is not Rome.

**Verification limits:** Historical/franchise/rebranding ambiguity and present-tense based after closure prevent an unqualified recommendation. No target-only substitution repairs this issue.

Sources: [S25](https://en.wikipedia.org/wiki/Fastjet_Tanzania), [S26](https://en.wikipedia.org/wiki/Fly540).

### p12: recommended_for_independent_review

Query ID: `5a87c13f5542996e4f30890c`

In what city did the "Prince of tenors" star in a film based on an opera by Giacomo Puccini?

Gold: **Rome**. Proposed target: **Milan**.

**Correct-answer investigation:** The intended tenor is Franco Corelli; his 1956 Tosca was made at Cinecittà in Rome.

**Candidate falsehood:** Milan is a different city from the checked filming location.

**Semantic compatibility:** Italian-city-to-Italian-city is a close contextual match.

**Aliases and ambiguity:** Franco/Dario Franco Corelli is not Mario Lanza. Rome/Roma and Milan/Milano are separate city aliases.

**Verification limits:** Correct the earlier preparation note that named Mario Lanza. State the filming-location interpretation explicitly; nickname and performance-city wording need reviewer confirmation.

Sources: [S27](https://www.treccani.it/enciclopedia/dario-franco-corelli_(Dizionario-Biografico)/), [S28](https://en.wikipedia.org/wiki/Tosca_(1956_film)), [S29](https://reneseghers.nl/prince-of-tenors/).

### p13: recommended_for_independent_review

Query ID: `5ae143ed55429920d5234360`

In what year was the university where Sergei Aleksandrovich Tokarev was a professor founded?

Gold: **1755**. Proposed target: **1838**.

**Correct-answer investigation:** MSU archive confirms Tokarev’s appointment; university history gives founding year 1755.

**Candidate falsehood:** 1838 contradicts that institution’s checked founding year.

**Semantic compatibility:** Both are plausible university founding years in the same answer unit.

**Aliases and ambiguity:** Sergei/Sergey and MSU/Lomonosov naming variants resolve to the same scholar/university; calendar conversion leaves the year 1755.

**Verification limits:** Do not substitute Tokarev’s appointment year for university founding. Sources are institutional, with one Russian-language biography.

Sources: [S30](https://www.letopis.msu.ru/peoples/8427), [S31](https://www.phys.msu.ru/eng/about/history/).

### p14: needs_revision

Query ID: `5adf37a95542995ec70e8f97`

The 2011–12 VCU Rams men's basketball team, led by third year head coach Shaka Smart, represented Virginia Commonwealth University which was founded in what year?

Gold: **1838**. Proposed target: **1755**.

**Correct-answer investigation:** VCU officially distinguishes 1838 institutional roots from creation of the merged university in 1968.

**Candidate falsehood:** 1755 is supported by neither VCU founding convention, but a false target does not resolve ambiguous gold semantics.

**Semantic compatibility:** A year substitution is coherent; the question’s founding-event definition is unresolved.

**Aliases and ambiguity:** VCU, MCV and RPI are related institutional histories, not interchangeable founding events.

**Verification limits:** Hold the frozen query/gold unchanged. Obtain an explicit founding convention or replace the question; never silently rewrite gold to 1968.

Sources: [S32](https://www.vcu.edu/about-vcu/vision-and-history/).

**Unverified replacement lead** — query `5ab4107a554299753aec5a2f`:

The Dogwoman telemovies were created by an actress born in what year?

Gold: 1961; proposed target: 1945; development source: `5ae531695542990ba0bbb1fb`.

Use the development Dogwoman-creator birth-year question (1961) with development year 1945.

Limits: Requires external verification of creator identity and birth year; the replacement has not been factually cleared.

### p15: recommended_for_independent_review

Query ID: `5a88f7855542993b751ca8da`

In what year did a movie that starred both Nicholas Cage and Cher come out?

Gold: **1987**. Proposed target: **1989**.

**Correct-answer investigation:** AFI identifies Moonstruck, Cher/Cage and initial US release in 1987.

**Candidate falsehood:** 1989 is not the checked initial-release year.

**Semantic compatibility:** Two nearby calendar years provide a coherent release-year substitution.

**Aliases and ambiguity:** Nicholas is a question spelling error for Nicolas Cage, not a different lead actor.

**Verification limits:** Recommendation uses initial-release-year convention; no assertion that every territorial release or rerelease occurred in 1987.

Sources: [S33](https://catalog.afi.com/Catalog/moviedetails/57753?mobile-app=true&theme=false).

### p16: recommended_for_independent_review

Query ID: `5ac546975542993e66e8229a`

What year was the early consumer co-operative, in which a 2012 British biographical feature film tells the story of, formed?

Gold: **1844**. Proposed target: **1876**.

**Correct-answer investigation:** Heritage custodian confirms the Rochdale society’s 1844 origin; film reference connects the 2012 biopic.

**Candidate falsehood:** 1876 conflicts with the checked foundation/opening year.

**Semantic compatibility:** A nineteenth-century foundation-year alternative is type- and event-compatible.

**Aliases and ambiguity:** Rochdale Society of Equitable Pioneers/Rochdale Equitable Pioneers Society name variations identify the same society.

**Verification limits:** Avoid the overclaim first cooperative ever. Full commissioning press release was blocked; the film link uses secondary corroboration.

Sources: [S34](https://www.co-operativeheritage.coop/blog/by-wheelbarrow-or-water-175-years-of-co-operation?title=by-wheelbarrow-or-water-175-years-of-co-operation), [S35](https://en.wikipedia.org/wiki/The_Rochdale_Pioneers).

### p17: recommended_for_independent_review

Query ID: `5ae531695542990ba0bbb1fb`

In what year was the coach who led the 2007 South Carolina Gamecocks football team in his third season as USC head coach born?

Gold: **1945**. Proposed target: **1961**.

**Correct-answer investigation:** University records identify Spurrier’s third USC season in 2007; historical-society biography gives birth in 1945.

**Candidate falsehood:** 1961 contradicts the checked birth year.

**Semantic compatibility:** Both are calendar birth years; 1961 is plausible for a coach active in 2007 without importing unrelated units.

**Aliases and ambiguity:** Steve Spurrier is the identified coach; USC here means South Carolina, not Southern California. The year 1961 is not a date-format alias for 1945.

**Verification limits:** Third-season reasoning is an inference from 2005–2007 records; birth evidence is scholarly secondary, not a birth record.

Sources: [S36](https://storage.googleapis.com/gamecocksonline-com/2018/08/6cd542f5-history.pdf), [S37](https://tennesseeencyclopedia.net/entries/steve-spurrier/).

### p18: recommended_for_independent_review

Query ID: `5ae518655542993aec5ec139`

Ken Pruitt  was a Republican member of an upper house of the legislature with how many members ?

Gold: **40 members**. Proposed target: **87**.

**Correct-answer investigation:** The contemporary 2002–04 Senate handbook establishes Pruitt’s membership and 40 senators.

**Candidate falsehood:** 87 is contradicted by the contemporary chamber-size statement.

**Semantic compatibility:** An integer member count is coherent; the candidate’s church-count source establishes provenance only.

**Aliases and ambiguity:** 40 members and 40 normalize to the same quantity semantically, but 87 is distinct.

**Verification limits:** Use the contemporary handbook instead of relying solely on today’s Senate page; preserve member units in any reviewed assertion.

Sources: [S38](https://www.flsenate.gov/UserContent/Publications/SenateHandbooks/pdf/2002-04_Senate_Handbook.pdf).

### p19: reject

Query ID: `5ae32e125542991a06ce9946`

According to the 2001 census, what was the population of the city in which Kirton End is located?

Gold: **35,124**. Proposed target: **48,982**.

**Correct-answer investigation:** 35,124 is supported only for Boston town by the checked council search excerpt; Kirton End is a separate hamlet in the borough.

**Candidate falsehood:** 48,982 differs from the town figure, but the question has no sound city-containing-the-hamlet referent.

**Semantic compatibility:** Reject the question/target pair: borough, town, parish and city boundaries are conflated.

**Aliases and ambiguity:** Boston town is not Boston borough or Boston, Massachusetts. Kirton End lies outside the town, not inside a city named Boston.

**Verification limits:** Full 2001 census table not independently opened. A numerical target replacement cannot repair the geographic premise; preserve frozen data and replace this review question.

Sources: [S39](https://en.wikipedia.org/wiki/Kirton_End), [S40](https://www.dorsetcouncil.gov.uk/documents/35024/281420/MTC004.pdf/a777a5c7-9feb-8c1b-3b35-6136b7d75cdd).

**Unverified replacement lead** — query `5ab4314955429942dd415ecd`:

Profile Lake is located at the foot of a mountain that is how many feet tall?

Gold: 4080; proposed target: 4145 ft; development source: `5a8ec55f5542995a26add50c`.

Use the Profile Lake mountain-height question: 4080 feet versus development target 4145 ft, retaining feet and a plausible magnitude.

Limits: Check Cannon Mountain identity, survey precision and elevation conventions independently. The replacement is unverified; source value comes from a highway-height question.

### p20: needs_revision

Query ID: `5a7cb8bc554299452d57b9be`

What is the capacity of the stadium that is the home ground of the Lahore Eagles?

Gold: **27,000**. Proposed target: **35,124**.

**Correct-answer investigation:** The development artifact records historical 27,000, whereas the PCB indexed 2025 statement reports 35,000 after rebuilding.

**Candidate falsehood:** 35,124 is not the indexed exact PCB value, but is close to a later approximate capacity and cannot be treated as timeless falsehood.

**Semantic compatibility:** Person-count capacity is the right unit; missing temporal anchoring is the substantive issue.

**Aliases and ambiguity:** Gaddafi/Lahore Stadium refer to the venue; Lahore Eagles and later teams/renovations must not be conflated.

**Verification limits:** Primary PCB page returned 403; indexed excerpt only. Establish an explicit historical capacity snapshot or replace the query; do not overwrite the frozen gold.

Sources: [S41](https://www.pcb.com.pk/press-release-detail/pcb-provides-stadia-upgradation-update.html).

**Unverified replacement lead** — query `5ae22eae554299495565da30`:

What was the 2010 population of the town where Black Crescent Mountain was located?

Gold: 310; proposed target: 729 at the 2010 census; development source: `5ac3d9135542995c82c4ac4c`.

Use the development 2010 Black Crescent Mountain town-population question, gold 310, with target 729 at the 2010 census.

Limits: Both are development census-count answers with the same stated year; town identity, boundaries, source and falsehood still require independent verification.

### p21: recommended_for_independent_review

Query ID: `5a877dd65542993e715abf79`

Were Halldór Laxness and Timothy Leary from the same country?

Gold: **no**. Proposed target: **yes**.

**Correct-answer investigation:** Publisher biography places Laxness’s origin in Iceland; NYPL archive places Leary’s birth in Massachusetts.

**Candidate falsehood:** Yes contradicts distinct origins under the conventional from interpretation.

**Semantic compatibility:** Boolean negation preserves the exact answer space.

**Aliases and ambiguity:** Halldór Kiljan Laxness and Timothy Francis Leary naming variants do not merge identities. Historical Danish sovereignty over Iceland does not make either origin US.

**Verification limits:** From means origin here, not whether both later lived in the same country. Keep this interpretation explicit.

Sources: [S42](https://www.penguinrandomhouse.com/authors/16935/halldor-laxness/), [S43](https://old-digitalcollections.nypl.org/collections/timothy-leary-papers?sub_collections_page=1).

### p22: recommended_for_independent_review

Query ID: `5a81711455429938b614233e`

Are both "Cooking Light" and "Vibe" magazines?

Gold: **yes**. Proposed target: **no**.

**Correct-answer investigation:** Publisher identifies Cooking Light as a magazine; Vibe’s historical magazine identity is corroborated.

**Candidate falsehood:** No contradicts both publications having magazine status under the historical publication-type reading.

**Semantic compatibility:** Boolean negation is semantically compatible.

**Aliases and ambiguity:** Cooking Light and Vibe are distinct titles; digital Vibe is a brand continuation, not a different gold alias.

**Verification limits:** Current print cessation/frequency does not negate historical magazine status. Official Vibe/ProQuest pages failed; Vibe evidence is secondary.

Sources: [S44](https://support.people.inc/hc/en-us/categories/4410136858391-Cooking-Light), [S45](https://en.wikipedia.org/wiki/Vibe_(magazine)).

### p23: recommended_for_independent_review

Query ID: `5a8dee2455429917b4a5bce1`

What other film did the star of 127 Hours act in?

Gold: **Pineapple Express**. Proposed target: **The Big Lebowski**.

**Correct-answer investigation:** Studios identify Franco as 127 Hours lead and a Pineapple Express performer.

**Candidate falsehood:** Franco is absent from the checked expanded Big Lebowski cast: a credits-based exclusion, not a film-viewing proof.

**Semantic compatibility:** A contemporary feature-film title is a coherent actor-filmography substitution.

**Aliases and ambiguity:** Pineapple Express is one valid answer among many; The Big Lebowski is not a title alias. James and Dave Franco must not be conflated.

**Verification limits:** Independent reviewer should verify complete/end credits and the lead-actor interpretation. Do not infer that any non-gold film is false.

Sources: [S46](https://www.20thcenturystudios.com/movies/127-hours), [S47](https://www.sonypictures.com/movies/pineappleexpress), [S48](https://en.wikipedia.org/wiki/The_Big_Lebowski).

### p24: needs_revision

Query ID: `5a8555ea5542992a431d1b07`

The movie that was the directorial debut of Jonathan Glazer included the musical piece Lujon. Which other movie that has the letter "B" in it also includes this piece?

Gold: **The Big Lebowski**. Proposed target: **Robot Overlords**.

**Correct-answer investigation:** References support Lujon in Sexy Beast and The Big Lebowski and identify Glazer’s feature debut.

**Candidate falsehood:** No complete Robot Overlords cue sheet was accessed; Henson’s score credit does not prove that licensed Lujon/Slow Hot Wind is absent.

**Semantic compatibility:** Robot Overlords contains B and is a film, but tone/context match is weaker and falsehood remains unresolved.

**Aliases and ambiguity:** Check Lujon/Slow Hot Wind and licensed arrangements, not just exact track spelling. Original score albums are not complete film soundtracks.

**Verification limits:** Needs music-cue/end-credit evidence; absence from search results is not evidence of absence. A replacement is only a new lead, not a verified improvement.

Sources: [S49](https://en.wikipedia.org/wiki/Lujon), [S50](https://en.wikipedia.org/wiki/Sexy_Beast), [S51](https://www.christianhensonmusic.com/), [S52](https://www.soundtrack.net/movie/robot-overlords/).

**Unverified replacement lead** — query `5a8555ea5542992a431d1b07`:

The movie that was the directorial debut of Jonathan Glazer included the musical piece Lujon. Which other movie that has the letter "B" in it also includes this piece?

Gold: The Big Lebowski; proposed target: Double Agent; development source: `5a776a805542993735360269`.

Double Agent is an exact development film title containing B and may be a more stylistically coherent alternative to investigate.

Limits: Not verified as false; a complete cue sheet is still needed, including Lujon/Slow Hot Wind. Do not submit it as a cleared replacement.

## Accessed-source catalogue

Claims below are scoped paraphrases, not copied articles. Locator sections help reviewers reopen the relevant content.

### S01

[Source](https://www.televisionacademy.com/bios/laurie-metcalf) — professional_institution; opened; accessed 2026-10-25.

Claim supported: Metcalf played Jackie in Roseanne and Debbie Loomis/Salt in Scream 2.

Locator: Biography, opening two paragraphs

Limits: Supports the stated fact only; no independent target approval.

### S02

[Source](https://en.wikipedia.org/wiki/Rosie_O'Donnell) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Rosie (Roseann) O’Donnell is a comedian, actress and talk-show host.

Locator: Lead and filmography

Limits: Filmography is not an exhaustive negative certificate; Roseann as a personal name does not establish a Roseanne TV credit.

### S03

[Source](https://en.wikipedia.org/wiki/Scream_2) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: The listed Scream 2 cast includes Metcalf; O’Donnell is not listed.

Locator: Cast

Limits: Absence from a secondary cast list is a credits-based inference, not proof against every uncredited appearance.

### S04

[Source](https://d23.com/a-to-z/scarlet-letter-the-film/) — studio_archive; opened; accessed 2026-10-25.

Claim supported: The 1995 Scarlet Letter stars Moore, Oldman and Duvall; Oldman plays Dimmesdale.

Locator: Disney A to Z entry

Limits: Lead billing alone does not enumerate every actor.

### S05

[Source](https://en.wikipedia.org/wiki/The_Scarlet_Letter_(1995_film)) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: The expanded credited cast lists Oldman and other English actors, but not Ejiofor.

Locator: Cast

Limits: Do not treat a missing cast-list entry as exhaustive proof about uncredited work.

### S06

[Source](https://en.wikipedia.org/wiki/Chiwetel_Ejiofor) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Ejiofor was born in Forest Gate, London; he is a British actor.

Locator: Lead; Early life

Limits: London birth supports the English-actor interpretation; nationality labels and birthplace are distinct properties.

### S07

[Source](https://www.paramountpressexpress.com/cbs-media-ventures/shows/flip-side/talent/?view=jaleel-white-2) — broadcaster_biography; opened; accessed 2026-10-25.

Claim supported: Jaleel White was cast as Steve Urkel in Family Matters in 1989.

Locator: Talent biography

Limits: Supports the stated fact only; no independent target approval.

### S08

[Source](https://en.wikipedia.org/wiki/Ben_Savage) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Ben Savage is an American actor known as Cory Matthews in Boy Meets World.

Locator: Lead; television filmography

Limits: Cory Matthews and Steve Urkel are different characters; check any alleged alternate portrayal against episode credits.

### S09

[Source](https://www.jkrowling.com/wp-content/uploads/2025/03/J.K.-Rowling-Biography-2025.pdf) — author_official; opened; accessed 2026-10-25.

Claim supported: Rowling wrote the seven-book Harry Potter series.

Locator: Page 1, biography opening

Limits: Supports the stated fact only; no independent target approval.

### S10

[Source](https://en.wikipedia.org/wiki/Rupert_Grint) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Grint portrayed Ron Weasley in the Harry Potter films.

Locator: Filmography, Harry Potter entries

Limits: Supports the stated fact only; no independent target approval.

### S11

[Source](https://www.amacad.org/person/jane-m-mayer) — professional_institution; opened; accessed 2026-10-25.

Claim supported: Mayer is a journalist and writer of nonfiction books.

Locator: Member biography

Limits: This is not an exhaustive bibliography or proof she never wrote fiction.

### S12

[Source](https://www.televisionacademy.com/bios/nick-offerman) — professional_institution; opened; accessed 2026-10-25.

Claim supported: Offerman played Ron Swanson in Parks and Recreation.

Locator: Biography opening

Limits: Supports the stated fact only; no independent target approval.

### S13

[Source](https://en.wikipedia.org/wiki/November_(2004_film)) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: November credits Offerman as Officer Roberts, not Christopher Rich.

Locator: Cast

Limits: Secondary credit list; 2004 festival premiere and 2005 theatrical release distinguish this title from other films named November.

### S14

[Source](https://en.wikipedia.org/wiki/Christopher_Rich_(actor)) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Christopher Rich Wilson is the actor associated with Murphy Brown and Reba.

Locator: Lead; filmography

Limits: Disambiguate from the historical theatre manager; omission of Parks and Recreation is not an exhaustive negative proof.

### S15

[Source](https://banffmediafestival.playbackonline.ca/2022/speakers/968857/justinspitzer/) — industry_speaker_biography; opened; accessed 2026-10-25.

Claim supported: Spitzer created and executive-produced Superstore.

Locator: Speaker biography

Limits: Page template mixes event-year labels; use the explicit career statement, not navigation dates.

### S16

[Source](https://www.bluenotejazz.com/hawaii/tm-event/johnny-pemberton/) — performer_event_biography; opened; accessed 2026-10-25.

Claim supported: Pemberton plays Bo on NBC’s Superstore.

Locator: Performer biography

Limits: Promotional biography; corroboration is preferable for the exact full character name.

### S17

[Source](https://en.wikipedia.org/wiki/Rob_Sitch) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Robert Ian Sitch is Rob Sitch, an Australian writer, producer, director and comedy performer.

Locator: Lead and career

Limits: Career summary is not exhaustive; the Superstore creator attribution comes from S15.

### S18

[Source](https://www.kulturportali.gov.tr/turkiye/istanbul/gezilecekyer/atik-valide-camii) — government_heritage; opened; accessed 2026-10-25.

Claim supported: Atik Valide Mosque is in Üsküdar, Istanbul.

Locator: Location and address

Limits: Turkish-language heritage entry; Turkey inference uses the modern location, not Ottoman-era national borders.

### S19

[Source](https://en.wikipedia.org/wiki/Valens_Aqueduct) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: The Valens aqueduct is in Istanbul, Turkey, also named Bozdoğan Kemeri.

Locator: Lead and location

Limits: Supports the stated fact only; no independent target approval.

### S20

[Source](https://www.jrkyushu.co.jp/english/train/htb.html) — railway_operator; opened; accessed 2026-10-25.

Claim supported: JR Kyushu’s Huis Ten Bosch train runs to Huis Ten Bosch station.

Locator: Routing and train configuration

Limits: Does not itself establish the park’s Dutch theme.

### S21

[Source](https://en.wikipedia.org/wiki/Huis_Ten_Bosch_(theme_park)) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: The Japanese Huis Ten Bosch park recreates the Netherlands.

Locator: Theme and lead

Limits: Netherlands is the theme country, not the physical location; Holland is a common partial geographic label.

### S22

[Source](https://plato.stanford.edu/entries/strauss-leo/) — scholarly_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Strauss was born in Kirchhain, Germany, and wrote Thoughts on Machiavelli.

Locator: Life and Work; bibliography

Limits: The question says Thoughts of, not the published title Thoughts on; historical birthplace was in the German Empire.

### S23

[Source](https://www.20thcenturystudios.com/movies/gone-girl) — studio_official; opened; accessed 2026-10-25.

Claim supported: Gone Girl was released in 2014 and includes Carrie Coon.

Locator: Release Date and Cast

Limits: Does not establish Margo’s character name or the fictional state setting by itself.

### S24

[Source](https://en.wikipedia.org/wiki/Gone_Girl_(film)) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Coon plays Margo Dunne; the principal disappearance narrative is set in Missouri.

Locator: Cast, lead and plot

Limits: The film also contains New York backstory; the inference concerns its principal setting, not every scene.

### S25

[Source](https://en.wikipedia.org/wiki/Fastjet_Tanzania) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Fastjet Tanzania originated as Fly540 Tanzania, associated with Kenya-based Fly540.

Locator: History

Limits: Distinguish the Tanzanian airline, Kenyan company, franchise, and later parent ownership; the airline subsequently ceased operations.

### S26

[Source](https://en.wikipedia.org/wiki/Fly540) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Five Forty Aviation, trading as Fly540, was based in Nairobi, Kenya.

Locator: Lead and headquarters

Limits: Historical headquarters; present-tense based is unsafe for a ceased airline. The linked archived company contact was not opened.

### S27

[Source](https://www.treccani.it/enciclopedia/dario-franco-corelli_(Dizionario-Biografico)/) — scholarly_biography; opened; accessed 2026-10-25.

Claim supported: Corelli played Cavaradossi in Gallone’s 1956 Tosca, filmed at Cinecittà.

Locator: 1956 film paragraph

Limits: Italian-language biography; does not alone establish the nickname or Rome location.

### S28

[Source](https://en.wikipedia.org/wiki/Tosca_(1956_film)) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Corelli stars in the Puccini-based Tosca film made at Cinecittà in Rome.

Locator: Lead

Limits: Filming location and opera setting are conceptually distinct even when both resolve to Rome here.

### S29

[Source](https://reneseghers.nl/prince-of-tenors/) — biographer_official; opened; accessed 2026-10-25.

Claim supported: The biographer’s Prince of Tenors book concerns Franco Corelli.

Locator: Title

Limits: Identifies the intended nickname referent; it is not an exclusive trademark or nickname registry.

### S30

[Source](https://www.letopis.msu.ru/peoples/8427) — university_archive; opened; accessed 2026-10-25.

Claim supported: Tokarev was a professor and headed the MSU ethnography department.

Locator: Biography and department chair entry

Limits: Russian-language university source; transliterations Sergei/Sergey refer to the same scholar.

### S31

[Source](https://www.phys.msu.ru/eng/about/history/) — university_official; opened; accessed 2026-10-25.

Claim supported: Moscow State University was founded in 1755.

Locator: History opening

Limits: Julian/Gregorian dates differ within the same year, not by 83 years.

### S32

[Source](https://www.vcu.edu/about-vcu/vision-and-history/) — university_official; opened; accessed 2026-10-25.

Claim supported: VCU traces roots to 1838, while the merger creating VCU occurred in 1968.

Locator: A history of breaking with tradition

Limits: Both dates have official support for different institutional meanings; the frozen question does not specify which.

### S33

[Source](https://catalog.afi.com/Catalog/moviedetails/57753?mobile-app=true&theme=false) — film_institution_catalog; opened; accessed 2026-10-25.

Claim supported: Moonstruck stars Cher and Nicolas Cage and initially opened in December 1987.

Locator: Cast and Release Date

Limits: US initial release, not every international release or later rerelease; the question misspells Nicolas.

### S34

[Source](https://www.co-operativeheritage.coop/blog/by-wheelbarrow-or-water-175-years-of-co-operation?title=by-wheelbarrow-or-water-175-years-of-co-operation) — heritage_custodian; opened; accessed 2026-10-25.

Claim supported: The Rochdale pioneers organised and opened their cooperative store in 1844.

Locator: August meeting and December opening paragraphs

Limits: Earlier cooperatives existed; this verifies this society, not an absolute first-ever claim.

### S35

[Source](https://en.wikipedia.org/wiki/The_Rochdale_Pioneers) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: The Rochdale Pioneers is a 2012 biographical film about founding the Rochdale cooperative.

Locator: Lead

Limits: Independent film identity corroboration is desirable; commissioning press release could not be opened.

### S36

[Source](https://storage.googleapis.com/gamecocksonline-com/2018/08/6cd542f5-history.pdf) — university_athletics_guide; opened; accessed 2026-10-25.

Claim supported: Spurrier coached South Carolina in 2005, 2006 and 2007.

Locator: Year-by-year records, printed page 122

Limits: Third-season identification is an explicit inference from consecutive years.

### S37

[Source](https://tennesseeencyclopedia.net/entries/steve-spurrier/) — historical_society_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Spurrier was born on April 20, 1945.

Locator: Biography

Limits: Biographical secondary reference, not a birth certificate.

### S38

[Source](https://www.flsenate.gov/UserContent/Publications/SenateHandbooks/pdf/2002-04_Senate_Handbook.pdf) — government_contemporary_handbook; opened; accessed 2026-10-25.

Claim supported: The 2002–04 Florida Senate had 40 members and included Republican Ken Pruitt.

Locator: PDF pages 3 and 12 (zero-based 2 and 11)

Limits: Contemporary to his service; 87 is a different count, not a member-count alias.

### S39

[Source](https://en.wikipedia.org/wiki/Kirton_End) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Kirton End is a hamlet in Kirton parish, Boston district, southwest of Boston town.

Locator: Lead

Limits: District membership does not place a hamlet within Boston town; the question’s city premise is unsafe.

### S40

[Source](https://www.dorsetcouncil.gov.uk/documents/35024/281420/MTC004.pdf/a777a5c7-9feb-8c1b-3b35-6136b7d75cdd) — government_hosted_consultant_report; search_excerpt_only; accessed 2026-10-25.

Claim supported: The indexed table lists Boston town at 35,124 in the 2001 census.

Locator: Search excerpt, Table C.2

Limits: Full PDF could not be parsed/opened; do not describe this as a full-document verification.

### S41

[Source](https://www.pcb.com.pk/press-release-detail/pcb-provides-stadia-upgradation-update.html) — venue_governing_body; search_excerpt_only; accessed 2026-10-25.

Claim supported: PCB’s January 2025 release reports Gaddafi Stadium capacity increased to 35,000.

Locator: Search excerpt, Upgrades at Gaddafi Stadium

Limits: Full open returned 403; checked indexed excerpt only. It contradicts treating 27,000 as timeless.

### S42

[Source](https://www.penguinrandomhouse.com/authors/16935/halldor-laxness/) — author_publisher; opened; accessed 2026-10-25.

Claim supported: Laxness was born near Reykjavík, Iceland.

Locator: Author biography

Limits: From is interpreted as origin, not temporary residence.

### S43

[Source](https://old-digitalcollections.nypl.org/collections/timothy-leary-papers?sub_collections_page=1) — archive_custodian; opened; accessed 2026-10-25.

Claim supported: Leary was born in Springfield, Massachusetts.

Locator: Biographical/historical notes

Limits: Origins differ even though both people lived abroad; historical Icelandic sovereignty does not make the origins the same.

### S44

[Source](https://support.people.inc/hc/en-us/categories/4410136858391-Cooking-Light) — publisher_support; opened; accessed 2026-10-25.

Claim supported: The Cooking Light publisher explicitly identifies it as a magazine.

Locator: Magazine section

Limits: A publisher help category is sufficient for publication type, not current print frequency.

### S45

[Source](https://en.wikipedia.org/wiki/Vibe_(magazine)) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Vibe is a music and entertainment magazine, with a historical print edition.

Locator: Lead and publication history

Limits: A digital transition does not erase the historical magazine classification; present print status is not the question.

### S46

[Source](https://www.20thcenturystudios.com/movies/127-hours) — studio_official; opened; accessed 2026-10-25.

Claim supported: James Franco plays Aron Ralston in 127 Hours.

Locator: Synopsis and Cast

Limits: Other actors also appear; star is interpreted as the leading performer.

### S47

[Source](https://www.sonypictures.com/movies/pineappleexpress) — studio_official; opened; accessed 2026-10-25.

Claim supported: James Franco plays the dealer in Pineapple Express.

Locator: Synopsis

Limits: Establishes one valid answer; the open-ended question has many valid film answers.

### S48

[Source](https://en.wikipedia.org/wiki/The_Big_Lebowski) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: The expanded credited cast does not include James Franco.

Locator: Cast

Limits: Credits-based exclusion; uncredited appearances were not established by watching end credits. The films have different casts, not title aliases.

### S49

[Source](https://en.wikipedia.org/wiki/Lujon) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Mancini’s Lujon appears in Sexy Beast and The Big Lebowski.

Locator: Henry Mancini recording

Limits: Also called Slow Hot Wind; the film list is not exhaustive and cannot exclude Robot Overlords.

### S50

[Source](https://en.wikipedia.org/wiki/Sexy_Beast) — secondary_encyclopedia; opened; accessed 2026-10-25.

Claim supported: Sexy Beast is Jonathan Glazer’s feature directing debut.

Locator: Lead

Limits: Feature-film debut is distinct from earlier advertising/music-video direction.

### S51

[Source](https://www.christianhensonmusic.com/) — composer_official; opened; accessed 2026-10-25.

Claim supported: Henson lists Robot Overlords among his scoring projects.

Locator: Scoring projects

Limits: Original-score authorship does not exclude licensed Mancini music or alternate track titles.

### S52

[Source](https://www.soundtrack.net/movie/robot-overlords/) — specialist_soundtrack_catalog; opened; accessed 2026-10-25.

Claim supported: Robot Overlords credits Henson as composer and lists a soundtrack album.

Locator: Credits

Limits: A score-album listing is not a complete film music cue sheet.

### S53

[Source](https://madeleinelengle.com/) — author_estate_official; opened; accessed 2026-10-25.

Claim supported: L’Engle wrote A Wrinkle in Time.

Locator: Biography opening

Limits: Supports the replacement’s youth science-fantasy background; does not independently approve a Harry Potter false target.

### S54

[Source](https://www.miramax.com/movie/frida/) — studio_official; opened; accessed 2026-10-25.

Claim supported: Frida lists Mía Maestro and director Julie Taymor.

Locator: Starring and Director

Limits: Page incorrectly labels release 2001; do not use that field to verify the development question’s 2002 date.

### S55

[Source](https://catalog.afi.com/Film/54006-FRIDA) — film_institution_catalog; search_excerpt_only; accessed 2026-10-25.

Claim supported: The indexed AFI Frida record attributes direction to Taymor and describes its 2002 release context.

Locator: Search excerpt

Limits: Full page was not opened in this audit; only the returned search excerpt was accessed.

## Unavailable or incomplete access

- [Attempted source](https://www.discover-nagasaki.com/en/featured-topics/huistenbosch): 503 on full open; primary park-theme verification unavailable.
- [Attempted source](https://www.co-operative.coop/media/news-releases/tv-premiere-for-inspirational-new-movie-about-the-birth-of-co-operatives-): 403 on full open; replaced with heritage custodian plus secondary film reference.
- [Attempted source](https://www.nobelprize.org/prizes/literature/1955/laxness/biographical/): 403 on full open; used opened publisher biography.
- [Attempted source](https://archives.nypl.org/mss/18595): 403 on full open; used opened NYPL digital-collections biography.
- [Attempted source](https://dev-about.proquest.com/en/products-services/the-vibe-archive/): 404 on full open; Vibe fact uses secondary reference.
- [Attempted source](https://about.proquest.com/en/products-services/the-vibe-archive/): 404 on full open.
- [Attempted source](https://www.vibe.com/about-us/): 402 on full open.
- [Attempted source](https://www.itv.com/news/granada/2012-11-01/story-of-co-operative-movement-founders-to-premiere): robots.txt unreachable on full open.
- [Attempted source](https://www.whatsong.org/movie/the-big-lebowski): 403 on full open; not used as checked primary evidence.
- [Attempted source](https://d23.com/gallery/disney-world-boy-meets-world/): Opened page body lacks the indexed Cory Matthews caption; used secondary actor biography instead.
- [Attempted source](https://www.pcb.com.pk/press-release-detail/pcb-provides-stadia-upgradation-update.html): 403 on full open; S41 is explicitly indexed-excerpt-only.
- [Attempted source](https://www.dorsetcouncil.gov.uk/documents/35024/281420/MTC004.pdf/a777a5c7-9feb-8c1b-3b35-6136b7d75cdd): PDF not parsed as text on full open; S40 is explicitly indexed-excerpt-only.

## Independent review and remaining blockers

Use the v3-reviewed approval instructions in README.md only after independent factual and semantic assessment. Do not turn preparer classifications into approval fields.
Resolve weak negative evidence, subtype/genre fit, corporate timelines, institutional founding conventions and soundtrack cue coverage. Reject malformed premises rather than modifying frozen questions or gold labels.
No targets are approved. The reviewed runner/manifest/replay integration remains incomplete. No held-out matrix or real-model generation was run.

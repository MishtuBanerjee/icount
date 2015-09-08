# icount
A personalized log to track, monitor, and analyze health information for chronic conditions 

________________


INTRODUCTION


My daughter began her adventures in counting with her own unique style, "1, 3, 6, 9", pulling out a rice grain, a macaroni noodle, or a blueberry with each count. Her twin brother, by contrast, prefers to count in Spanish while climbing stairs. Each is unique in predilection, personality, and health.  ICount is a simple template for a health log that you can make as unique as your child (or yourself). My wife and I developed it because our daughter has a severe form of epilepsy, requiring us to maintain logs of her seizures, medications, and observations on her condition before, during, and after seizures. Initially we looked to some of the pre set forms used for epilepsy, then upon finding them inflexible, switched to detail notes based on the clinical practice of Pediatric Occupational Therapists. As the need to sort out this information to increase our own understanding of medications, seizures, indications of incipient seizure conditions we've taken to developing a coded form that takes allows one to take flexible notes, but also supports analysis of the data.

ICount consists of three parts. 
- First the ICount protocol for coding observations. This protocol allows one to have much of the freedom of detailed notes, while also supporting coding observations in a way that can be analyzed to look for relationships amongst the observations.
- Second, ICount is a data file template. The file format is CSV, a simple format compatible with a wide range of data analysis software, including spreadsheets. 
- Third, ICount is a set of basic calculations that can be made from the coded data, and some software to help with the calculations. The ICount calculations are very simple ratios of counts. No pre knowledge of data science or analytics is assumed. You can do all these calculations by hand, with a calculater, or in a spreadsheet. They help you identify variables that are associated with each other, across observations (what is called correlation and regression analysis), using only count data -- to help you explore trends and identify patterns in your observations. 

While we have tried to make ICount a general protocol for health observations, feel free to clone and customize to your needs.
_________________

CODING PROTOCOL

The coding protocol is designed to handle development of qualitative codes from observing events, as well as quantitative measures that might come from various monitoring devices. It allows you to develop a customized coding system.


Mention ABC tracking form
Mention purpose of behaviour

_________________

DATA FORMAT

|Date|Time|Event|ObservationID|ObservationType|ObservedVariable|ObservationValue|ObservationConfidence|Observer|Subject|Comments|


_________________

BASIC CALCULATIONS


_________________

DATA MODEL

Note -- this section is more technical, and shows how the 11 columns are related via a relational data model. The data model allows construction of software to simplify data entry and querying the data.

Entities:
- people (and roles)
- observations and observation types
- variables
- observation values and confidence
- comment; essentially a special kind of variable

_________________

REFERENCES

- Bijou, et al. 1968 [ABC Monitoring](http://www.ncbi.nlm.nih.gov/pmc/articles/PMC1310995/pdf/jaba00084-0079.pdf)
- Downey, A.B. 2012. [Think Bayes. Bayesian Statistics Made Simple](http://www.greenteapress.com/thinkbayes/). Green Tea Press.
- Easley, D. and Kleinberg, 2010. J. Networks, Crowds, and Markets. Reasoning About A Highly Connected World. Cambridge University Press.
Good. P.I. 2005. Introduction to Statistics Through Resampling Methods and R/S-Plus. Wiley-Interscience.
- Guilhoto et al. 2011. [Higher evening antiepileptic drug dose for nocturnal and early-morning seizures](http://www.sciencedirect.com/science/article/pii/S1525505010007365) Epilepsy and Behaviour 20:334-337.
- Hempel,C.G. 1966. Philosophy of Natural Science. Prentice Hall.
- Hilbe, J.H. 2014. Modelling Count Data. Cambridge University Press.
- Meadows, D.H. 2008. Thinking In Systems. a Primer. Chelsea Green Publishing.
- Pearl, J. 2000. Causality. Models, Reasoning, and Inference. Cambridge University Press.
- Ramgopal et al. 2014. [Seizure detection, seizure prediction, and closed-loop warning systems in epilepsy](http://www.sciencedirect.com/science/article/pii/S1525505014002297) Epilepsy and Behaviour. 37: 291-307.
- Stone, J.V. 2013. Bayes' Rule. A Tutorial Introduction to Bayesian Analysis. Sebtel Press.
- Wickham, H. 2014. [Tidy Data](http://www.jstatsoft.org/v59/i10/paper)

_________________

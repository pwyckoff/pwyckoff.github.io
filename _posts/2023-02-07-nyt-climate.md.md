---
title: "Climate Change in the New York Times"
layout: single
excerpt: "How has coverage of climate change in the NYT evolved since 1995? Analysis using the NYT API and quantitative text analysis tools such as Quanteda. " 
date: "2023-02-20"
permalink: /posts/2023/02/nyt-climate
tags: 
  - climate change
  - data analysis
  - media
  - text analysis
---

Mediatic attention has a significant impact on the politics of climate
change (see Maxwell Boykoff’s work, for example). In this post, I use
the New York Times’ API to assess how it has covered climate change over
the past few decades.

The dataset for the analysis is the subset of NYT articles from
1995-2022 that included climate change terms in their abstract\*.

I look at: 
* the frequency of climate change articles over time, by
desk and by published page to get a sense of how the salience of climate
change coverage has evolved over time 
* word use in the abstracts 
* climate change and natural disasters

For more detail about the code used to compile the dataset, take a look
at the github version of this document.

# A larger share of coverage, a new desk, moving up the pages

This section highlights the increasing coverage dedicated to climate
change over the period through various indicators.

## Frequency overall, over time

![](/images/unnamed-chunk-3-1.png)

As a share of all articles published each month, climate change 
articles have become a larger share in recent years. As will be visible 
in future charts, the 2005-2010 saw an increase in coverage before stagnation 
in the early 2010s. It’s only since 2015 that the share of articles discussing 
climate change has regularly been above the 0.5% threshold.

In the chart above, it’s also clear that there seems to be some kind of
seasonal pattern to the publishing. 

![](/images/unnamed-chunk-4-1.png)

These charts suggest that generally there tend to be more
articles published toward the end of the year, and in June.

## Frequency by desk

In the next section, I look to see how coverage has shifted between
desks.

The following table highlights the variation in aggregated NYT desks (I
aggregated desk codes that likely reflect historical shifts in naming
(e.g. Business vs. Business Desk), and put all desks with fewer than 100
articles into their own “other” category). The National, Foreign and
Editorial desks have a significant share of articles, reflecting their
historic dominance and significant size. A significant number are either
unclassified or in smaller desks.

    ## 
    ##     Books  Business   Climate   Culture Editorial   Foreign   Letters    Metro. 
    ##       111       406       449       136       571       585       107       243 
    ##  National      None      OpEd     Other   Science 
    ##       584       867       394       694       293

![](/images/unnamed-chunk-7-1.png)![](/images/unnamed-chunk-7-2.png)

These charts provide a significant amount of information.

Some basic notes:

* The charts highlights the creation of the new climate desk at the NYT
in 2017[url](https://www.nytimes.com/2017/03/16/insider/a-sea-change-for-climate-coverage.html),
with about 450 articles written by that desk since, nearly 10% of the
total number of articles in our sample. *It also highlights the seeming
creation of new tags for letters and op-eds mid-way through the sample.

* Beyond that, looking at the data, there's a concentration of
articles in the book section around 2005-2007 (the era of Al Gore’s An
Inconvenient Truth), and over the past three years. There are a perhaps
surprisingly large (and continuous) number of articles from the Business
desk, also peaking around 2006-2007. 

* Looking at the different geographic desks, it is striking that the flow is more or less constant
for the Foreign desk, has larger peaks in 2009 and 2016 for the National
desk, and is definitely focused around 2006 for the Metropolitan desk.

## Frequency by Page Number

Next, I turn to the page numbers – which gives a sense to the relative
importance accorded to climate change as a topic on any single day.

![](/images/unnamed-chunk-8-1.png)

There generally seems to be a relatively constant page rank for articles
about climate change – but it seems likely that earlier years are
influenced by having relatively few articles. There does seem to be a
downward trend “towards the front” in the past decade.


![](/images/unnamed-chunk-9-1.png)

One way around the issues with the previous chart is to just focus on
front page stories (aka print page 1). Indeed, over the past five years,
there has been an increase in the number of more front page stories
about climate change. The peaks of front page coverage were in May 2006
(an Inconvenient Truth was released on May 24) and October of 2021.

# Presidents and Scientists, Nation and World

I'll now use quanteda to dig a little deeper into what words are used
in the abstracts.

![](/images/unnamed-chunk-10-1.png)![](/images/unnamed-chunk-10-2.png)

These exercises to determine the frequency of words used in articles
reveal some key insights. For one thing, *political leaders* stand out –
“Presid”, but also specifically Bush and Obama. Other actors that are
key to these debates, and to press discussion, are *scientists*,
mentioned nearly 500 times. Perhaps ironically in the context of global
collective action debates, *“nation” and “world”* are #11 and #12 in
frequency, respectively. As a last note – it is perhaps not surprising
to see how much *money* (“$”) gets mentioned in these articles.

# Natural disasters

## Coverage of disasters in NYT climate change articles
Finally, the rest of this project will be focused on looking at how
natural disasters drive coverage of climate policy, using a dictionary
for natural disasters to sort through our existing corpus of articles.

![](/images/unnamed-chunk-11-1.png)

Indeed, while the number of climate change articles has been increasing
generally, it is also seems like there are more articles specifically
referencing natural disasters as part of the coverage.

## Estimates of impact of natural disasters covered in NYT articles about climate change

For this next and final section, I go to wikipedia to gather some data
on the impact of these natural disasters that are mentioned in articles
referencing climate change. By hand, I went through and skimmed the
selected abstracts for references, and then found the relevant wikipedia
page url. There are not English wikipedia pages for all disasters.

As discussed, the NYT is increasingly touching upon specific natural
disasters in its climate change coverage. Many of the disasters
mentioned were devastating in terms of human and economic costs.

It’s worth noting that most of this coverage remains of US and Western
European disasters – despite our understanding that these places will
not necessarily face the biggest challenges. And indeed, looking at word
counts, it is striking that articles above 1,000 words are focused on
natural disasters in the West.

<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<style>body{background-color:white;}</style>
<script src="nyt_climate_plotly/htmlwidgets-1.5.4/htmlwidgets.js"></script>
<script src="nyt_climate_plotly/plotly-binding-4.10.0/plotly.js"></script>
<script src="nyt_climate_plotly/typedarray-0.1/typedarray.min.js"></script>
<script src="nyt_climate_plotly/jquery-3.5.1/jquery.min.js"></script>
<link href="nyt_climate_plotly/crosstalk-1.2.0/css/crosstalk.min.css" rel="stylesheet" />
<script src="nyt_climate_plotly/crosstalk-1.2.0/js/crosstalk.min.js"></script>
<link href="nyt_climate_plotly/plotly-htmlwidgets-css-2.5.1/plotly-htmlwidgets.css" rel="stylesheet" />
<script src="nyt_climate_plotly/plotly-main-2.5.1/plotly-latest.min.js"></script>
  <title>plotly</title>
</head>
<body>
<div id="htmlwidget_container">
  <div id="htmlwidget-498ad52a2b0771bb974a" style="width:100%;height:400px;" class="plotly html-widget"></div>
</div>
<script type="application/json" data-for="htmlwidget-498ad52a2b0771bb974a">{"x":{"data":[{"x":[17977,18088,18145,18234,18500,18500,18515,18576,19354],"y":[975,1196,676,1548,1511,1511,1712,719,844],"text":["disaster: 2019 Midwestern U.S. floods<br />casualties: 3<br />damage: $2.9 billion ($1.6 billion in Iowa; $1.3 billion in Nebraska)","disaster: Hurricane Barry (2019)<br />casualties: 2 total<br />damage: $600 million (2019 USD)","disaster: Hurricane Dorian<br />casualties: 84 total, 245 missing<br />damage: ≥ $5.1 billion (2019 USD)(Costliest in Bahamian history)","disaster: 2019 European heat waves<br />casualties: 3,951+ deaths (Belgium: 716; France: 1,435; Germany: 500; Netherlands: 400; United Kingdom: 900)<br />damage: ","disaster: Hurricane Laura<br />casualties: 47 direct, 34 indirect<br />damage: ≥ $23.3 billion (2020 USD)","disaster: 2020 Atlantic hurricane season<br />casualties: ≥ 417 total<br />damage: > $51.114 billion  (2020 USD)","disaster: 2020 Western United States wildfire season<br />casualties: 47 direct (32 in California, 11 in Oregon, 1 in Washington, 1 in Arizona, 2 in Colorado)<br />damage: >$19.884 billion (2020 USD)","disaster: 2020 Atlantic hurricane season<br />casualties: ≥ 417 total<br />damage: > $51.114 billion  (2020 USD)","disaster: December 2022 North American winter storm<br />casualties: 106<br />damage: $5.4 billion"],"type":"scatter","mode":"markers","marker":{"autocolorscale":false,"color":"rgba(248,118,109,1)","opacity":1,"size":5.66929133858268,"symbol":"circle","line":{"width":1.88976377952756,"color":"rgba(248,118,109,1)"}},"hoveron":"points","name":"Climate","legendgroup":"Climate","showlegend":true,"xaxis":"x","yaxis":"y","hoverinfo":"text","frame":null},{"x":[10440],"y":[479],"text":"disaster: 1998 Florida wildfires<br />casualties: 0<br />damage: >$300,000,000 in timber alone. ","type":"scatter","mode":"markers","marker":{"autocolorscale":false,"color":"rgba(196,154,0,1)","opacity":1,"size":5.66929133858268,"symbol":"circle","line":{"width":1.88976377952756,"color":"rgba(196,154,0,1)"}},"hoveron":"points","name":"Magazine","legendgroup":"Magazine","showlegend":true,"xaxis":"x","yaxis":"y","hoverinfo":"text","frame":null},{"x":[15645,16328,17030,17407,18036,18872],"y":[713,770,1181,628,863,873],"text":["disaster: Hurricane Sandy<br />casualties: 233 total<br />damage: $68.7 billion (2012 USD)(Seventh-costliest hurricane in U.S. history)","disaster: 2014 India–Pakistan floods<br />casualties: 557 277 in India<br />damage: 2,550 villages affected","disaster: 2016 Louisiana floods<br />casualties: 13<br />damage: $10–15 billion","disaster: Hurricane Harvey<br />casualties: 107 total<br />damage: $125 billion (2017 USD)(Tied as costliest tropical cyclone on record)","disaster: 2019–20 Australian bushfire season<br />casualties: <br />damage: $920 million - $3.65 billion AUD","disaster: Hurricane Ida<br />casualties: 107 total<br />damage: $75.25 billion (2021 USD)(Sixth-costliest tropical cyclone on record)"],"type":"scatter","mode":"markers","marker":{"autocolorscale":false,"color":"rgba(83,180,0,1)","opacity":1,"size":5.66929133858268,"symbol":"circle","line":{"width":1.88976377952756,"color":"rgba(83,180,0,1)"}},"hoveron":"points","name":"Opinion","legendgroup":"Opinion","showlegend":true,"xaxis":"x","yaxis":"y","hoverinfo":"text","frame":null},{"x":[13940,14799,15086],"y":[1207,466,493],"text":["disaster: 2008 Chinese winter storms<br />casualties: at least 129<br />damage: At least 151.65 billion Chinese yuan ($21.94 billion US$)","disaster: 2010 Northern Hemisphere heat waves<br />casualties: 55,000 in Russia alone, ~2,600 outside Russia<br />damage: ~$500 billion (2011 USD)","disaster: 2011 Texas wildfires<br />casualties: 10 total (6 civilians, 4 firefighters)<br />damage: $513.9 million (2011 USD)"],"type":"scatter","mode":"markers","marker":{"autocolorscale":false,"color":"rgba(0,192,148,1)","opacity":1,"size":5.66929133858268,"symbol":"circle","line":{"width":1.88976377952756,"color":"rgba(0,192,148,1)"}},"hoveron":"points","name":"Science","legendgroup":"Science","showlegend":true,"xaxis":"x","yaxis":"y","hoverinfo":"text","frame":null},{"x":[17840],"y":[2134],"text":"disaster: 2018 California wildfires<br />casualties: 97 civilians and 6 firefighters<br />damage: >$26.347 billion (2018 USD) (Costliest on record)","type":"scatter","mode":"markers","marker":{"autocolorscale":false,"color":"rgba(0,182,235,1)","opacity":1,"size":5.66929133858268,"symbol":"circle","line":{"width":1.88976377952756,"color":"rgba(0,182,235,1)"}},"hoveron":"points","name":"Travel","legendgroup":"Travel","showlegend":true,"xaxis":"x","yaxis":"y","hoverinfo":"text","frame":null},{"x":[13050,17792,18827,18843],"y":[536,1575,257,1217],"text":["disaster: Hurricane Katrina<br />casualties: 1,392 total<br />damage: $125 billion (2005 USD)(Tied as costliest tropical cyclone on record)","disaster: Hurricane Matthew<br />casualties: 603 total<br />damage: $16.47 billion (2016 USD)(Costliest in Haitian history)","disaster: 2021 British Isles heat wave<br />casualties: <br />damage: ","disaster: 2021 Arizona wildfires<br />casualties: 2<br />damage: "],"type":"scatter","mode":"markers","marker":{"autocolorscale":false,"color":"rgba(165,138,255,1)","opacity":1,"size":5.66929133858268,"symbol":"circle","line":{"width":1.88976377952756,"color":"rgba(165,138,255,1)"}},"hoveron":"points","name":"U.S.","legendgroup":"U.S.","showlegend":true,"xaxis":"x","yaxis":"y","hoverinfo":"text","frame":null},{"x":[12306,15882,18131,18567,18843],"y":[95,453,905,903,1148],"text":["disaster: 2002 European floods<br />casualties: 232 <br />damage: €27.7 billion","disaster: 2013 North India floods<br />casualties: 6,054<br />damage: 4,550 villages were affected ","disaster: 2019 Amazon rainforest wildfires<br />casualties: 2<br />damage: >$900 billion (2019 USD)","disaster: Typhoon Goni<br />casualties: 32 total<br />damage: $1.02 billion (2020 USD)","disaster: 2021 Western North America heat wave<br />casualties: ≥1,408 deaths (estimated), ≥914 (confirmed). ~600-800 deaths in Canada (deadliest weather event in the history of Canada) and ~200-600 deaths in the US<br />damage: "],"type":"scatter","mode":"markers","marker":{"autocolorscale":false,"color":"rgba(251,97,215,1)","opacity":1,"size":5.66929133858268,"symbol":"circle","line":{"width":1.88976377952756,"color":"rgba(251,97,215,1)"}},"hoveron":"points","name":"World","legendgroup":"World","showlegend":true,"xaxis":"x","yaxis":"y","hoverinfo":"text","frame":null}],"layout":{"margin":{"t":45.3588829941669,"r":7.30593607305936,"b":41.7789743183678,"l":48.9497716894977},"plot_bgcolor":"rgba(255,255,255,1)","paper_bgcolor":"rgba(255,255,255,1)","font":{"color":"rgba(0,0,0,1)","family":"","size":14.6118721461187},"title":{"text":"Climate change articles mentioning specific natural disasters, 1995-2022","font":{"color":"rgba(0,0,0,1)","family":"","size":17.5342465753425},"x":0,"xref":"paper"},"xaxis":{"domain":[0,1],"automargin":true,"type":"linear","autorange":false,"range":[9994.3,19799.7],"tickmode":"array","ticktext":["2000","2005","2010","2015","2020"],"tickvals":[10957,12784,14610,16436,18262],"categoryorder":"array","categoryarray":["2000","2005","2010","2015","2020"],"nticks":null,"ticks":"outside","tickcolor":"rgba(51,51,51,1)","ticklen":3.65296803652968,"tickwidth":0.66417600664176,"showticklabels":true,"tickfont":{"color":"rgba(77,77,77,1)","family":"","size":11.689497716895},"tickangle":-0,"showline":false,"linecolor":null,"linewidth":0,"showgrid":true,"gridcolor":"rgba(235,235,235,1)","gridwidth":0.66417600664176,"zeroline":false,"anchor":"y","title":{"text":"Date","font":{"color":"rgba(0,0,0,1)","family":"","size":14.6118721461187}},"hoverformat":".2f"},"yaxis":{"domain":[0,1],"automargin":true,"type":"linear","autorange":false,"range":[-6.95,2235.95],"tickmode":"array","ticktext":["0","500","1000","1500","2000"],"tickvals":[0,500,1000,1500,2000],"categoryorder":"array","categoryarray":["0","500","1000","1500","2000"],"nticks":null,"ticks":"outside","tickcolor":"rgba(51,51,51,1)","ticklen":3.65296803652968,"tickwidth":0.66417600664176,"showticklabels":true,"tickfont":{"color":"rgba(77,77,77,1)","family":"","size":11.689497716895},"tickangle":-0,"showline":false,"linecolor":null,"linewidth":0,"showgrid":true,"gridcolor":"rgba(235,235,235,1)","gridwidth":0.66417600664176,"zeroline":false,"anchor":"x","title":{"text":"Article Word Count","font":{"color":"rgba(0,0,0,1)","family":"","size":14.6118721461187}},"hoverformat":".2f"},"shapes":[{"type":"rect","fillcolor":"transparent","line":{"color":"rgba(51,51,51,1)","width":0.66417600664176,"linetype":"solid"},"yref":"paper","xref":"paper","x0":0,"x1":1,"y0":0,"y1":1}],"showlegend":true,"legend":{"bgcolor":"rgba(255,255,255,1)","bordercolor":"transparent","borderwidth":1.88976377952756,"font":{"color":"rgba(0,0,0,1)","family":"","size":11.689497716895},"title":{"text":"section","font":{"color":"rgba(0,0,0,1)","family":"","size":14.6118721461187}}},"hovermode":"closest","barmode":"relative"},"config":{"doubleClick":"reset","modeBarButtonsToAdd":["hoverclosest","hovercompare"],"showSendToCloud":false},"source":"A","attrs":{"55781db36481":{"x":{},"y":{},"colour":{},"disaster":{},"casualties":{},"damages":{},"type":"scatter"}},"cur_data":"55781db36481","visdat":{"55781db36481":["function (y) ","x"]},"highlight":{"on":"plotly_click","persistent":false,"dynamic":false,"selectize":false,"opacityDim":0.2,"selected":{"opacity":1},"debounce":0},"shinyEvents":["plotly_hover","plotly_click","plotly_selected","plotly_relayout","plotly_brushed","plotly_brushing","plotly_clickannotation","plotly_doubleclick","plotly_deselect","plotly_afterplot","plotly_sunburstclick"],"base_url":"https://plot.ly"},"evals":[],"jsHooks":[]}</script>
<script type="application/htmlwidget-sizing" data-for="htmlwidget-498ad52a2b0771bb974a">{"viewer":{"width":"100%","height":400,"padding":0,"fill":true},"browser":{"width":"100%","height":400,"padding":0,"fill":true}}</script>
</body>
</html>


# Closing thoughts

Analysis of the "newspaper of record" highlights how coverage of climate change has increased over the past few decades. 
* The total share of articles has quintupled, with a particular increase surrounding the release of Al Gore's An Inconvenient Truth. A similar trend can be observed in terms of front page articles. 
* Desks such as Business and Foreign contribute a significant number of articles on climate change.
* Key actors and dynamics emerge from word use analysis -- coverage emphasizes presidents and scientists, financial considerations, and both "nation" and "world." 
* Natural disasters coverage and climate change mentions seem to be increasingly linked. As we have become more aware of how the severity and frequency of natural disasters is linked to climate change, it does seem that the New York Times is making the connection more frequently.  

# Sources and Notes

The [NYT API](https://developer.nytimes.com/apis) is an excellent resource 
for textual analysis of its coverage. 

The analysis was conducted in R, in particular drawing from the 
[Quanteda](http://quanteda.io/) package for text analysis.  

The climate change terms used in the initial analysis are: “climate
change” “global warming” “greenhouse effect” “climate catastrophe”
“climate emergency” “climate crisis” and “global heating.” To select these terms, I drew from some
established work ([see Lineman et
al](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0138996),
or [Kumar and
Li](https://www.researchgate.net/profile/Sathish-Kumar-26/publication/331453828_Spatiotemporal_Topic_Modeling_and_Sentiment_Analysis_of_Global_Climate_Change_Tweets/links/5d9033e6a6fdcc2554a4740e/Spatiotemporal-Topic-Modeling-and-Sentiment-Analysis-of-Global-Climate-Change-Tweets.pdf)).
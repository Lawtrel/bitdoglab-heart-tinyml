% This class file is provided for authors submitting to the
% Modelagem e Simulação de Biossistemas Journal
%
% Version: 1.00, 2022/05/05
%
% Produced by Marcos Figueredo
%
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{MSBJournal}[2022/05/10, v1.00]
\AtEndOfClass{\RequirePackage{microtype}}

% Options for element switching
\RequirePackage{xifthen}
\newboolean{displaycopyright}
\newboolean{displaylineno}
\setboolean{displaylineno}{false}

% v2.2: Anais (proceedings) assembly support. \ifinanais is set by the
% Anais master document before \input-ing a paper, so this class is only
% loaded/\begin{document}'d once for the whole proceedings. Standalone
% compilation of a single paper is unaffected: \ifinanais stays false.
\@ifundefined{ifinanais}{\newif\ifinanais\global\inanaisfalse}{}
\newcommand{\anaispaperid}{}

\DeclareOption{lineno}{\setboolean{displaylineno}{true}}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{extarticle}}
\ProcessOptions*
\LoadClass{extarticle}

% April 16, 2016:
% Line numbers
% v1.8 April 12, 2018: make sure line numbers are
% displayed in outer margins of columns; so
% remove "running" option somehow gets it right
\RequirePackage[switch,pagewise]{lineno}
%v1.11 April 1, 2022: re-add line numbers that were accidentally removed in 1.10
\ifthenelse{\boolean{displaylineno}}{\linenumbers}{}

% Fonts and language
\RequirePackage[utf8]{inputenc}
\RequirePackage[english]{babel}
\RequirePackage{amsmath,amsfonts,amssymb}
\RequirePackage{mathpazo}
\RequirePackage[scaled]{helvet}
\RequirePackage[T1]{fontenc}
\RequirePackage{url}
\RequirePackage[colorlinks=true, allcolors=blue]{hyperref}
\RequirePackage{lettrine}

\newcommand{\watermarkfont}{\color{black50}\normalfont\fontsize{10}{12}\selectfont}
\newcommand{\headerfont}{\normalfont\fontsize{8}{10}\selectfont}
\newcommand{\headerifont}{\normalfont\fontsize{7}{9}\selectfont}
\newcommand{\titlefont}{\color{ppgmsbC3}\normalfont\sffamily\bfseries\fontsize{18}{22}\selectfont}
\newcommand\corresfont{\fontsize{9}{11}\selectfont}
\newcommand{\datesfont}{\normalfont\sffamily\itshape\fontsize{8}{10}\selectfont}
\renewcommand\UrlFont{\color{color1}\sffamily}
\newcommand{\absfont}{\normalfont\sffamily\linespread{1}\fontsize{8.9}{11}\selectfont}
\newcommand{\absheadfont}{\color{ppgmsbC3}\normalfont\sffamily\fontsize{9.4}{11}\selectfont}
\newcommand{\keywordsfont}{\normalfont\sffamily\linespread{1}\fontsize{8.9}{11}\selectfont}
\newcommand{\keywordheadfont}{\normalfont\sffamily\fontsize{7.8}{9}\selectfont\bfseries}
\newcommand{\copyrightfont}{\normalfont\sffamily\fontsize{7}{9}\selectfont}


\RequirePackage{datetime}

\newdateformat{monthyeardate}{%
	\monthname[\THEMONTH] \THEYEAR}

\RequirePackage{enumitem}
\setlist[itemize]{noitemsep}


% Author and affiliation
\RequirePackage{authblk}
\setlength{\affilsep}{9pt}
\renewcommand\Authfont{\color{color0}\fontsize{9.5}{11}\sffamily\selectfont}
\renewcommand\Affilfont{\color{color0}\fontsize{6.5}{9}\selectfont}
% \makeatletter
\renewcommand\AB@affilsep{\reset@font\protect\Affilfont}
\renewcommand\AB@affilsepx{\reset@font\protect\\\protect\Affilfont}
%\renewcommand\AB@affilsepx{, \protect\Affilfont}
% \makeatother
\renewcommand\Authands{ and }

% Choose article type
% v2.2: \input (not \RequirePackage) so switching type back and forth is
% re-appliable every time — needed once an Anais mixes full papers and
% extended abstracts in the same compilation. \providecommand gives the
% three type-specific commands a first definition to \renewcommand* over.
\providecommand{\articletypename}{\textbf{PAPER}}
\providecommand{\typeColorLogo}{ppgmsbC1}
\providecommand{\typeColorTitle}{ppgmsbC3}
\newcommand*{\articletype}[1]{%
	\input{#1.sty}}

% Copyright statement
\RequirePackage{textcomp} % For copyright symbol styling
\newcommand{\copyrightstatement}{Copyright \, \textcopyright\, \@confyear{} by Programa de Pós-Graduação em Modelagem e Simulação de Biossistemas}

% v1.6: Remove copyright statement from PDF
\AtBeginDocument{\setboolean{displaycopyright}{false}}

% Graphics, tables and other formatting
\RequirePackage{graphicx,xcolor}
\RequirePackage{colortbl}
\RequirePackage{booktabs}
\RequirePackage{tikz}
\RequirePackage{algorithm}
\RequirePackage[noend]{algpseudocode}
\RequirePackage{changepage}
\RequirePackage[left=48pt,%
right=42pt,%
top=48pt,%
bottom=60pt,%
headheight=15pt,%
headsep=10pt,%
letterpaper,twoside]{geometry}%
\RequirePackage[labelfont={bf,sf},%
list=no,%
labelsep=space,%
figurename=Figure,%
singlelinecheck=off,%
justification=RaggedRight]{caption}
\setlength{\columnsep}{24pt} % Distance between the two columns of text
\setlength{\parindent}{12pt} % Paragraph indent

% Set document color scheme
\definecolor{black50}{gray}{0.5} % 50% black for hrules
\definecolor{color0}{RGB}{0,0,0} % Base color
\definecolor{color1}{RGB}{59,90,198} % unused
\definecolor{color3}{RGB}{0,76,113} %
\definecolor{ppgmsbC1}{cmyk}{96,0,100,0}
\definecolor{ppgmsbC2}{RGB}{36,96,84}
\definecolor{ppgmsbC3}{RGB}{0,48,58}
\definecolor{abstractbg}{RGB}{234,244,236} % very light green background for the abstract box


% ppgmsbC3 defined by the specific article type style file

% Bibliography
% v2.0: bibtex removed. References are now typed manually with
% \bibitem inside a thebibliography environment (see the .tex template).
% natbib still provides \citep/\citet in author-year (APA-like) style;
% just make sure each \bibitem is written as \bibitem[Author(Year)]{key}.
\RequirePackage[authoryear,round]{natbib}
\setlength{\bibsep}{4pt}

% Table style
\arrayrulecolor{ppgmsbC2} % Set the color of the horizontal rules
\renewcommand{\arraystretch}{1.5} % Increased line spacing
\captionsetup[table]{position=below} % Reduce spacing below caption

% Algorithm style
% \makeatletter
\newcommand\fs@coloruled{\def\@fs@cfont{\bfseries}\let\@fs@capt\floatc@coloruled
	\def\@fs@pre{\kern2pt}%
	\def\@fs@post{\kern2pt{\color{ppgmsbC3}\hrule}\relax}%
	\def\@fs@mid{\kern2pt{\color{ppgmsbC3}\hrule}\kern2pt}%
	\let\@fs@iftopcapt\iftrue}
% \makeatother

\floatstyle{coloruled}
\restylefloat{algorithm}

% Headers and footers
\RequirePackage{fancyhdr}  % custom headers/footers
\RequirePackage{lastpage}  % Number of pages in the document
\pagestyle{fancy}          % Enables the custom headers/footers

\newif\ifslugprint\global\slugprintfalse

% v2.0: box widened and label shrunk so longer labels (e.g. "RESUMO
% EXPANDIDO") fit alongside the shorter "ARTIGO COMPLETO".
\def\ouplogo{{\fboxsep0pt\fcolorbox{\typeColorLogo}{\typeColorLogo}{\textcolor{white}{\vbox to 62pt{\vfil\hbox to 150pt{\hfil\fontsize{10}{11}\selectfont \articletypename \hfil}\vspace*{10pt}}}}}\hspace*{12pt}}

\def\slugnote{\global\slugprinttrue}

\def\slugline{\vbox to 0pt{\vspace*{9.5pt}{\headerfont SBMSB, \@confyear \vskip-6pt}%
		\rule{121pt}{2pt}\par%
		{\headerifont\color{ppgmsbC3} DOI: \@confdoi\vskip1pt}%
		{\headerifont \@confname\par}%
		{\headerfont \rec\\
			\rev \\	\acc}}}

\def\firstpageimage{%
	\begin{picture}(0,0)%
		\put(0,-27){\ouplogo}%
		\put(163,-20){\includegraphics[width=.7in]{logoOnly}}%
\end{picture}}

\fancypagestyle{firststyle}{
	\fancyhead[LO,RE,LE,RO]{}
	\ifslugprint\fancyhead[R]{\slugline}\else\fi%
	\fancyhead[L]{\firstpageimage}
	% v1.6: Remove volume and month information
	%    \fancyfoot[R]{\footnotesize Genetics, Vol. XXX, XXXX–XXXX \hspace{1em} \monthyeardate\today \hspace{2em} \thepage\ }
}

% Headers
\fancyhead[LO,RE,LE,RO]{} % Blank headers for non-title pages.
% Footers
\lfoot{}
\cfoot{}
\rfoot{}
% \makeatletter
\fancyhead[RO]{\@runningauthor\hspace{2em}\thepage}
\fancyhead[LE]{\thepage\hspace{2em}\@runningtitle}
% \makeatother
\fancyfoot[LO,RE]{}
\renewcommand{\headrulewidth}{0pt}% % No header rule
\renewcommand{\footrulewidth}{0pt}% % No footer rule

%% 13 July 2016: make sure sections are unnumbered
\setcounter{secnumdepth}{0}
\setcounter{tocdepth}{0}

% Section/subsection/paragraph set-up
\RequirePackage[explicit]{titlesec}
\renewcommand{\thesubsection}{\Alph{subsection}}

\titleformat{\section}
{\large\sffamily\bfseries\color{ppgmsbC3}}
{\thesection.}
{0.5em}
{#1}
[]
\titleformat{name=\section,numberless}
{\large\sffamily\bfseries\color{ppgmsbC3}}
{}
{0em}
{#1}
[]
\titleformat{\subsection}
{\bfseries\fontsize{10}{12}\selectfont}
{\thesubsection.}
{0.5em}
{#1}
[]
\titleformat{\subsubsection}[runin]
{\sffamily\bfseries\itshape}
{\thesubsubsection.}
{0.5em}
{#1}
[]
\titleformat{\paragraph}[runin]
{\sffamily\small\bfseries}
{}
{0em}
{#1}
\titlespacing*{\section}{0pc}{3ex \@plus4pt \@minus3pt}{5pt}
\titlespacing*{\subsection}{0pc}{2.5ex \@plus3pt \@minus2pt}{2pt}
\titlespacing*{\subsubsection}{0pc}{2ex \@plus2.5pt \@minus1.5pt}{2pt}
\titlespacing*{\paragraph}{0pc}{1.5ex \@plus2pt \@minus1pt}{12pt}

% Article meta data additional fields
\newcommand{\runningauthor}[1]{\def\@runningauthor{#1}}
%% Backward compatibility
\newcommand{\correspondingauthor}[1]{\runningauthor{#1}}
\newcommand{\keywords}[1]{\def\@keywords{#1}}
\newcommand{\runningtitle}[1]{\def\@runningtitle{#1}}

% v2.1: conference metadata, meant to be set from the .tex template
% (year, DOI, symposium name and review dates), so nothing event-specific
% is hardcoded in the class file.
\newcommand{\confyear}[1]{\gdef\@confyear{#1}}
\newcommand{\confname}[1]{\gdef\@confname{#1}}
\newcommand{\confdoi}[1]{\gdef\@confdoi{#1}}
\newcommand{\recdate}[1]{\gdef\@recdate{#1}}
\newcommand{\revdate}[1]{\gdef\@revdate{#1}}
\newcommand{\accdate}[1]{\gdef\@accdate{#1}}

% Defaults, overridden by the template file if needed.
\confyear{\the\year}
\confname{IV Bahia Symposium on Biosystems Modeling and Simulation}
\confdoi{10.1534/SBMSB.XXX.XXXXXX}
\recdate{xx/xx/\the\year}
\revdate{xx/xx/\the\year}
\accdate{xx/xx/\the\year}

\newcommand{\keywordname}{{\keywordheadfont Keywords:}} % Defines the keywords heading name

% Colored margin box
%\newcommand{\marginmark}{
	%\begin{textblock}{2}(200,9.5)
	%\begin{tikzpicture}
	%\fill[color=ppgmsbC3] (0,0) rectangle (1.2,0.25);
	%\end{tikzpicture}
	%\end{textblock}
	%}

\newcommand{\marginmark}{
	\begin{textblock}{2}(200,9.5)
		\begin{tikzpicture}
			\fill[color=ppgmsbC3] (0,0) rectangle (1.2,0.25);
		\end{tikzpicture}
	\end{textblock}
}


\def\xabstract{abstract}
\long\def\abstract#1\end#2{\def\two{#2}\ifx\two\xabstract
	\long\gdef\theabstract{\ignorespaces#1}
	\def\go{\end{abstract}}\else
\typeout{^^J^^J PLEASE DO NOT USE ANY \string\begin\space \string\end^^J
	COMMANDS WITHIN ABSTRACT^^J^^J}#1\end{#2}
\gdef\theabstract{\vskip12pt BADLY FORMED ABSTRACT: PLEASE DO
NOT USE {\tt\string\begin...\string\end} COMMANDS WITHIN
THE ABSTRACT\vskip12pt}\let\go\relax\fi
\go}

% Set environment for abstract content and styling
% v2.0: abstract (and keywords) now sit on a very light green
% background box, so the template reads the same whether it is
% used for a resumo expandido or for a full paper.
\newlength{\abstractboxsep}
\setlength{\abstractboxsep}{9pt}
\newcommand{\abscontent}{
\noindent
\colorbox{abstractbg}{%
\parbox{\dimexpr\linewidth-2\abstractboxsep\relax}{%
\vskip\abstractboxsep
{%
\parbox{\dimexpr\linewidth-2\abstractboxsep\relax}{%
	%% v1.8: turn on line numbers
	\ifthenelse{\boolean{displaylineno}}{\internallinenumbers}{}%
	{\absheadfont\bfseries Abstract}\vskip3.5pt \absfont \theabstract
}%
\vskip15.5pt%
\noindent
\parbox{\dimexpr\linewidth-2\abstractboxsep\relax}{%
	%% v1.8: turn on line numbers
	\ifthenelse{\boolean{displaylineno}}{\internallinenumbers}{}%
	{\keywordsfont\keywordname}\hspace*{0.1em} \keywordsfont \@keywords%
}%
}%
\vskip\abstractboxsep
}%
}%
}%

% Custom title page
\renewcommand{\@maketitle}{\bgroup\setlength{\parindent}{0pt}
{%
\vskip67pt%
{\raggedright \titlefont \@title\vskip13pt}%
{\raggedright \@author\vskip9.5pt}
\ifx\@corres\undefined\vskip6.5pt\else\@corres\vskip11.5pt\fi%
}\egroup%
{%
\vskip12pt%
\abscontent
}%
\vskip25pt%
% v2.2: when assembled into the Anais, tag the top of this paper with a
% label the proceedings summary can \pageref{} — see \anaispaperid below.
\ifinanais\ifx\anaispaperid\@empty\else\label{paper:\anaispaperid}\fi\fi%
}%

% v2.2: the LaTeX kernel's \maketitle self-nullifies \maketitle, \@maketitle,
% \title, \author, \date, \and and \thanks the moment it fires — harmless
% for a single standalone paper, but fatal for an Anais that calls
% \maketitle once per included paper (the second paper's title/author would
% print as raw body text). Save the working definitions and restore them
% globally right after each call so \maketitle stays reusable.
\let\SBMSB@kernelmaketitle\maketitle
\let\SBMSB@maketitlebody\@maketitle
\let\SBMSB@title\title
\let\SBMSB@author\author
\let\SBMSB@date\date
\let\SBMSB@and\and
\let\SBMSB@thanks\thanks
\newcommand{\SBMSB@wrappermaketitle}{%
	\SBMSB@kernelmaketitle
	\global\let\maketitle\SBMSB@wrappermaketitle
	\global\let\@maketitle\SBMSB@maketitlebody
	\global\let\title\SBMSB@title
	\global\let\author\SBMSB@author
	\global\let\date\SBMSB@date
	\global\let\and\SBMSB@and
	\global\let\thanks\SBMSB@thanks
}
\let\maketitle\SBMSB@wrappermaketitle

% Other packages
\RequirePackage{enumitem} % For reducing bullet list item separation

\RequirePackage{tabularx}

\RequirePackage[flushmargin,ragged]{footmisc}

\newlength{\myFootnoteWidth}%
\newlength{\myFootnoteLabel}%
\setlength{\myFootnoteLabel}{0.5em}
\renewcommand{\@makefntext}[1]{%
\setlength{\myFootnoteWidth}{\columnwidth}%
\addtolength{\myFootnoteWidth}{-\myFootnoteLabel}%
\noindent\makebox[\myFootnoteLabel][r]{\@makefnmark\ }%
\parbox[t]{\myFootnoteWidth}{#1}
}

\newdimen\footrulechange
\footrulechange\columnwidth
% Commands to set the footnote for the front page.
\renewcommand{\footnoterule}{%
\kern -3pt
{\color{black50} \hrule width \footrulechange height 0.5pt}
\kern 2.5pt
}

\newcommand{\@authfootnote}[2]{%
\begingroup
\setlength{\myFootnoteLabel}{0em}
\renewcommand\thefootnote{}\footnote{\footnotelayout\copyrightfont\textsuperscript{#1}#2}%
\endgroup%
}

\newcommand\blfootnote[1]{%
\@authfootnote{}{#1}%
%   \begingroup
%   \setlength{\myFootnoteLabel}{0em}
%   \renewcommand\thefootnote{}\footnote{#1}%
%   \addtocounter{footnote}{-1}%
%   \addtocounter{Hfootnote}{-1}%
%   \endgroup%
}
\newcommand\correspondingauthoraffiliation[2][]{%
\gdef\@corres{\corresfont\textsuperscript{#1}#2}%
}

\def\dates#1{\gdef\@dates{#1}}

\def\rec{\textbf{Received:} \@recdate.}
\def\rev{\textbf{Revised:} \@revdate}
\def\acc{\textbf{Accepted:} \@accdate}

\newcommand{\equalcontrib}[1]{\@authfootnote{#1}{These authors contributed equally to this work.}}

\newcommand{\firstpagefootnote}{\footrulechange\textwidth%
\blfootnote{\hsize\textwidth doi: \@confdoi \\%
\ifx\@dates\undefined\vskip0pt\else\@dates\vskip0pt\fi%
Published by Bahia State University \@confyear.
}}

\newenvironment{tableminipage}[1]{\begin{minipage}{#1}\renewcommand\footnoterule{ \kern -1ex}%
\setlength{\myFootnoteLabel}{0.5em}%
}{\end{minipage}}

\def\firstpagebreak{\break\newpage\noindent}

% Package to enable absolute positioning of figures
\RequirePackage[absolute,overlay]{textpos}
\setlength{\TPHorizModule}{1mm}
\setlength{\TPVertModule}{1mm}
\textblockorigin{0mm}{0mm} % start everything near the top-left corner

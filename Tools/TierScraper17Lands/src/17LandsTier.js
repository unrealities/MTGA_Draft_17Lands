const RATINGS_DICT = {"grid-row: 16":"NA", //"TBD"
                     "grid-row: 15":"SB", //"SB"
                     "grid-row: 14":"F ", //"F"
                     "grid-row: 13":"D-", //"D-" 
                     "grid-row: 12":"D ", //"D"
                     "grid-row: 11":"D+", //"D+"
                     "grid-row: 10":"C-", //"C-"
                     "grid-row: 9" :"C ",  //"C"
                     "grid-row: 8" :"C+",  //"C+"
                     "grid-row: 7" :"B-",  //"B-"
                     "grid-row: 6" :"B ",  //"B"
                     "grid-row: 5" :"B+",  //"B+"
                     "grid-row: 4" :"A-",  //"A-"
                     "grid-row: 3" :"A ",  //"A"
                     "grid-row: 2" :"A+"}  //"A+"
const COLUMN_PREFIX = "tier_text tier_bucket "
const COLOR_IDS = ["W","U","B","R","G","M","C","L"]
const EVENTS = ["pageshow"]

const EXTENSION_STARTUP = (event) => {
    const gridZone = document.getElementById('sortable_card_tiers_app');

    if(!document.getElementById('container_div')){
        const containerDiv = createScraperContainer();
        gridZone.insertBefore(containerDiv, gridZone.firstElementChild);
    }

    document.getElementById('tier_button').addEventListener('click', collectPickRatings);
};

function createScraperContainer(){
    const tierButton = createButton('tier_button', 'Download Tier List', 'width:100%');
    const tierLabelBox = createTextarea('tier_label_box', 1, 'width:100%', 'Enter Label Here!');

    const titleLink = createAnchorElement('https://github.com/FiYir/MTGA_Draft_17Lands/tree/main/Tools/TierScraper17Lands', 'MTGA_Draft_17Lands TierScraper');
    const containerTitle = document.createElement('div');
    containerTitle.id = 'title';
    containerTitle.appendChild(titleLink);

    const labelDiv = document.createElement('div');
    labelDiv.appendChild(tierLabelBox);

    const buttonDiv = document.createElement('div');
    buttonDiv.appendChild(tierButton);

    const containerBox = document.createElement('div');
    containerBox.id = 'content';
    containerBox.appendChild(labelDiv);
    containerBox.appendChild(buttonDiv);

    const containerDiv = document.createElement('div');
    containerDiv.className = 'title_container';
    containerDiv.id = 'container_div';
    containerDiv.appendChild(containerTitle);
    containerDiv.appendChild(containerBox);
    
    return containerDiv;
}

// Global function to create an anchor element
function createAnchorElement(href, text) {
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.textContent = text;
    return anchor;
}

// Global function to create a button element
function createButton(id, text, style) {
    const button = document.createElement('button');
    button.id = id;
    button.style = style;
    button.textContent = text;
    return button;
}

// Global function to create a textarea element
function createTextarea(id, rows, style, placeholder) {
    const textarea = document.createElement('textarea');
    textarea.id = id;
    textarea.rows = rows;
    textarea.style = style;
    textarea.spellcheck = false;
    textarea.placeholder = placeholder;
    return textarea;
}

function collectPickRatings() {
    const currentDate = new Date();
    const datetime = `${currentDate.getMonth() + 1}/${currentDate.getDate()}/${currentDate.getFullYear()} ${currentDate.getHours()}:${currentDate.getMinutes()}:${currentDate.getSeconds()}`;

    let ratingsObj = {};
    const tierLabel = collectLabel();
    const setName = collectSetName();

    ratingsObj.meta = {"collection_date": datetime, "label": tierLabel, "set": setName, "version": 3.0};
    ratingsObj.ratings = {};
    
    for (let i = 0; i < COLOR_IDS.length; i++) {
        ratingsObj = collectColumnRatings(COLOR_IDS[i], ratingsObj);
    }
    
    if (Object.keys(ratingsObj.ratings).length != 0){
        tierExport(ratingsObj);
    }
    else{
        console.error(`Ratings not available`);
    }
}

function collectColumnRatings(colorId, ratingsObj) {
    try {
        const tableRows = document.querySelectorAll(`[class^="${COLUMN_PREFIX}"][class*="${colorId}"]`);
        for (let i = 0; i < tableRows.length; i++) {
            let rowStyle = tableRows[i].getAttribute("style");
            rowStyle = rowStyle.match(/^grid-row: \d+/);
            const rowRating = (rowStyle) ? RATINGS_DICT[rowStyle[0]] : "";
            
            // Iterate through each column in this row
            const columnItems = tableRows[i].children;
            // Iterate through the items in this column
            for (let j = 0; j < columnItems.length; j++) {
                let cardName = columnItems[j].getElementsByClassName("tier_card_name");
                let cardComment = columnItems[j].getElementsByClassName("tier_card_comment");
                
                cardName = (cardName.length) ? cardName[0].innerHTML : "";
                cardComment = (cardComment.length) ? cardComment[0].innerHTML : "";
                const cardDict = {"rating": rowRating, "comment": cardComment};
                ratingsObj.ratings[cardName] = cardDict;
            }
        }
    } catch (error) {
        console.error(error);
    }
    
    return ratingsObj;
}

function collectSetName() {
    let setName = "";

    try {
        const tierListElement = document.getElementById("sortable_card_tiers_app");
        
        setName = tierListElement.dataset.expansion;
    
    } catch (error) {
        console.error(error);
    }
    
    return setName;
}

function collectLabel() {
    let tierLabel = "";
    
    try {
        tierLabel = document.querySelector("h2").textContent;
        
        // Check if a label was entered
        const customLabel = document.getElementById("tier_label_box").value;
        
        if (customLabel.length) {
            tierLabel = customLabel;
        }
        
    } catch (error) {
        console.error(error);
    }
    
    return tierLabel;
}

function tierExport(ratingsObj) {
    const url = document.URL.split("/");
    const filename = `Tier_${ratingsObj.meta.set}_${Date.now().toString()}.txt`;
    const tierObj = JSON.stringify(ratingsObj, null, 4); // indentation in JSON format, human readable
    const vBlob = new Blob([tierObj], { type: "octet/stream" });
    const vUrl = window.URL.createObjectURL(vBlob);
    
    const vLink = document.createElement("a");
    vLink.setAttribute("href", vUrl);
    vLink.setAttribute("download", filename);
    vLink.click();
}

EVENTS.forEach((eventName) =>
window.addEventListener(eventName, EXTENSION_STARTUP));

// Attach function to global scope for unit testing
window.collectColumnRatings = collectColumnRatings;
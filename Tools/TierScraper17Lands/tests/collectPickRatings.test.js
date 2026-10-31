/**
 * @jest-environment jsdom
 */

// Import the function under test
const contentScript = require('../src/17LandsTier.js');

// Define the test cases
const TEST_CASES = [
  ['<div class="tier_text tier_bucket shared W" style="grid-row: 2"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 1</div><div class="tier_card_comment">Comment 1</div></div></div>', 'W', 'Card 1', 'A+', 'Comment 1'],
  ['<div class="tier_text tier_bucket shared W" style="grid-row: 3;"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 2</div><div class="tier_card_comment">Comment 2</div></div></div>', 'W',  'Card 2', 'A ', 'Comment 2'],
  ['<div class="tier_text tier_bucket shared W" style="grid-row: 4 ;"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 3</div><div class="tier_card_comment">Comment 3</div></div></div>', 'W',  'Card 3', 'A-', 'Comment 3'],
  ['<div class="tier_text tier_bucket W" style="grid-row: 5 /"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 4</div><div class="tier_card_comment">Comment 4</div></div></div>', 'W',  'Card 4', 'B+', 'Comment 4'],
  ['<div class="tier_text tier_bucket W" style="grid-row: 6 / auto"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 5</div><div class="tier_card_comment">Comment 5</div></div></div>', 'W',  'Card 5', 'B ', 'Comment 5'],
  ['<div class="tier_text tier_bucket W" style="grid-row: 7 / auto;"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 6</div><div class="tier_card_comment">Comment 6</div></div></div>', 'W',  'Card 6', 'B-', 'Comment 6'],
  ['<div class="tier_text tier_bucket W" style="grid-row: 8/auto;"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 7</div><div class="tier_card_comment">Comment 7</div></div></div>', 'W',  'Card 7', 'C+', 'Comment 7'],
  ['<div class="tier_text tier_bucket W" style="grid-row: 9afdsaf;"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 8</div><div class="tier_card_comment">Comment 8</div></div></div>', 'W',  'Card 8', 'C ', 'Comment 8'],
  ['<div class="tier_text tier_bucket W" style="grid-row: 10 11"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 9</div><div class="tier_card_comment">Comment 9</div></div></div>', 'W',  'Card 9', 'C-', 'Comment 9'],
  ['<div class="tier_text tier_bucket W" style="grid-row: 11.12"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 10</div><div class="tier_card_comment">Comment 10</div></div></div>', 'W',  'Card 10', 'D+', 'Comment 10'],
  ['<div class="tier_text tier_bucket W" style="grid-row: 12"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 11</div><div class="tier_card_comment"></div></div></div>', 'W', 'Card 11', 'D ', ''],
  ['<div class="tier_text tier_bucket W" style="grid-row: 13"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 12 // Card 13</div><div class="tier_card_comment"></div></div></div>', 'W',  'Card 12 // Card 13', 'D-', ''],
  ['<div class="tier_text tier_bucket W" style="grid-row: 14"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 13</div></div>', 'W',  'Card 13', 'F ', ''],
  ['<div class="tier_text tier_bucket W" style="grid-row: 15"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 14</div></div>', 'W',  'Card 14', 'SB', ''],
  ['<div class="tier_text tier_bucket W" style="grid-row: 16"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 15</div></div>', 'W',  'Card 15', 'NA', ''],
  ['<div class="tier_text tier_bucket U" style="grid-row: 16"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 16</div></div>', 'U',  'Card 16', 'NA', ''],
  ['<div class="tier_text tier_bucket B" style="grid-row: 16"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 17</div></div>', 'B',  'Card 17', 'NA', ''],
  ['<div class="tier_text tier_bucket R" style="grid-row: 16"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 18</div></div>', 'R',  'Card 18', 'NA', ''],
  ['<div class="tier_text tier_bucket G" style="grid-row: 16"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 19</div></div>', 'G',  'Card 19', 'NA', ''],
  ['<div class="tier_text tier_bucket M" style="grid-row: 16"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 20</div></div>', 'M',  'Card 20', 'NA', ''],
  ['<div class="tier_text tier_bucket C" style="grid-row: 16"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 21</div></div>', 'C',  'Card 21', 'NA', ''],
  ['<div class="tier_text tier_bucket L" style="grid-row: 16"><div class="tier_card_preview tier_text tier_card rarity_M" data-rbd-draggable-context-id="0" data-rbd-draggable-id="18243"><div class="tier_card_name">Card 22</div></div>', 'L',  'Card 22', 'NA', ''],
  // Add more test cases here as needed
];

// Clear out the document body after every test
beforeEach(() => {
  document.body.innerHTML = '';
});

// Test cases for collectColumnRatings function
TEST_CASES.forEach(([html, sectionColor, expectedName, expectedGrade, expectedComment]) => {
    
  test(`collectColumnRatings correctly extracts data from HTML: ${html}`, () => {
    // Arrange: Set up any necessary test state or variables
    const containerDiv = document.createElement('div');
    containerDiv.innerHTML = html;

    // Append the container div to the document body
    document.body.appendChild(containerDiv);
    
    let ratingsObj = {"ratings" : {}};

    // Act: Call the function under test
    ratingsObj = window.collectColumnRatings(sectionColor,ratingsObj);

    // Assert: Check the result against the expected outcome
    expect(ratingsObj.ratings[expectedName]).toEqual({ rating: expectedGrade, comment: expectedComment });
  });
});

/**
 * Expired State Display for Process Owner Timers
 * Renders visual display for expired processes with JIRA ticket link and reset button
 * Uses ticket key from Confluence labels (Task 3: getTicketKeyFromLabel)
 *
 * IMPORTANT: ES5 syntax required for Confluence compatibility
 * - Use var instead of const/let
 * - Use function() instead of arrow functions
 */

// JIRA browse URL base
var JIRA_BROWSE_URL = 'https://jira.corp.adobe.com/browse/';

/**
 * Render the expired state display HTML
 * Format: [stopwatch emoji] EXPIRED  CPGNCX-63500  [ RESET ]
 *
 * @param {string} processId - The process ID from data-process-id attribute
 * @param {string} ownerUsername - The owner's username for ticket key lookup
 * @returns {string} - HTML string for expired state display
 */
function renderExpiredState(processId, ownerUsername) {
  // Get ticket key from label (stored by Task 3)
  var ticketKey = null;
  if (typeof window !== 'undefined' && window.MaptimizeJira && window.MaptimizeJira.getTicketKeyFromLabel) {
    ticketKey = window.MaptimizeJira.getTicketKeyFromLabel(ownerUsername);
  }

  var html = '<span class="expired-container">';

  // Expired text with stop sign emoji
  html += '<span class="expired">&#9940; EXPIRED</span>';

  // JIRA ticket link (if ticket exists)
  if (ticketKey) {
    var ticketUrl = JIRA_BROWSE_URL + ticketKey;
    html += '&nbsp;&nbsp;<a href="' + ticketUrl + '" target="_blank" class="jira-link">' + ticketKey + '</a>';
  }

  // Reset button with data-process-id for identification
  html += '&nbsp;&nbsp;<button type="button" class="reset-timer-btn" data-process-id="' + processId + '" data-owner-username="' + ownerUsername + '">RESET</button>';

  html += '</span>';

  return html;
}

/**
 * Update the display for an expired row
 * Replaces the content of .process-expiry span with expired state HTML
 *
 * @param {jQuery} $row - jQuery object for the table row
 */
function updateExpiredDisplay($row) {
  var $expirySpan = $row.find('.process-expiry');
  if ($expirySpan.length === 0) {
    return;
  }

  var processId = $row.data('process-id');
  var ownerUsername = $row.data('owner-username');

  if (!processId || !ownerUsername) {
    console.warn('[Maptimize] Missing required data attributes on row:', $row);
    return;
  }

  var expiredHtml = renderExpiredState(processId, ownerUsername);
  $expirySpan.html(expiredHtml);
}

/**
 * Update all expired rows with the expired state display
 * Should be called after JIRA tickets are created and labels are stored
 */
function updateAllExpiredDisplays() {
  $('tr[data-process-id]').each(function() {
    var $row = $(this);
    var $expirySpan = $row.find('.process-expiry');

    // Check if row is expired (has expired class or EXPIRED text)
    if ($expirySpan.hasClass('expired') || $expirySpan.text().indexOf('EXPIRED') !== -1) {
      updateExpiredDisplay($row);
    }
  });
}

// Export functions for external use and testing
if (typeof window !== 'undefined') {
  window.MaptimizeExpiredDisplay = {
    renderExpiredState: renderExpiredState,
    updateExpiredDisplay: updateExpiredDisplay,
    updateAllExpiredDisplays: updateAllExpiredDisplays,
    JIRA_BROWSE_URL: JIRA_BROWSE_URL
  };
}

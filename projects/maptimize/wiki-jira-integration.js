/**
 * JIRA Integration for Process Owner Timers
 * Creates JIRA tickets for expired processes with assignee and duplicate prevention
 * Uses Confluence labels for persistent state across all users/browsers
 */

// JIRA API configuration
var JIRA_API_ENDPOINT = 'https://wiki.corp.adobe.com/rest/jira-integration/1.0/issues?applicationId=5affdfe8-ed2e-3a17-8442-0790430373f0';
var JIRA_PROJECT_KEY = 'CPGNCX';
var JIRA_ISSUE_TYPE = 'Request';

// Label prefixes for duplicate prevention and ticket key storage
var LABEL_PREFIX_EXPIRED = 'maptimize_expired_';
var LABEL_PREFIX_TICKET = 'maptimize_ticket_';

/**
 * Check if a process-specific expired label exists on the current page
 * @param {string} ownerUsername - The owner's username (e.g., 'sheive')
 * @returns {boolean} - True if the expired label exists
 */
function hasProcessLabel(ownerUsername) {
  var labelName = LABEL_PREFIX_EXPIRED + ownerUsername;
  var labels = AJS.Labels.getLabels() || [];
  return labels.some(function(label) {
    return label.name === labelName;
  });
}

/**
 * Add a process-specific expired label to the current page
 * @param {string} ownerUsername - The owner's username
 * @param {function} callback - Optional callback after label is added
 */
function addProcessLabel(ownerUsername, callback) {
  var labelName = LABEL_PREFIX_EXPIRED + ownerUsername;
  AJS.Labels.addLabel(labelName, function() {
    console.log('[Maptimize] Added expired label:', labelName);
    if (callback) callback();
  });
}

/**
 * Store the created JIRA ticket key in a Confluence label
 * Format: maptimize_ticket_[username]_[CPGNCX-XXXXX]
 * @param {string} ownerUsername - The owner's username
 * @param {string} ticketKey - The JIRA ticket key (e.g., 'CPGNCX-63500')
 * @param {function} callback - Optional callback after label is added
 */
function storeTicketKeyLabel(ownerUsername, ticketKey, callback) {
  var labelName = LABEL_PREFIX_TICKET + ownerUsername + '_' + ticketKey;
  AJS.Labels.addLabel(labelName, function() {
    console.log('[Maptimize] Stored ticket key label:', labelName);
    if (callback) callback();
  });
}

/**
 * Retrieve the JIRA ticket key from Confluence labels for a specific owner
 * @param {string} ownerUsername - The owner's username
 * @returns {string|null} - The ticket key (e.g., 'CPGNCX-63500') or null if not found
 */
function getTicketKeyFromLabel(ownerUsername) {
  var labelPrefix = LABEL_PREFIX_TICKET + ownerUsername + '_';
  var labels = AJS.Labels.getLabels() || [];

  for (var i = 0; i < labels.length; i++) {
    var label = labels[i];
    if (label.name && label.name.indexOf(labelPrefix) === 0) {
      // Extract ticket key from label name
      // Label format: maptimize_ticket_[username]_[CPGNCX-XXXXX]
      var ticketKey = label.name.substring(labelPrefix.length);
      return ticketKey;
    }
  }
  return null;
}

/**
 * Remove expired and ticket labels for a specific owner (for reset functionality)
 * @param {string} ownerUsername - The owner's username
 * @param {function} callback - Optional callback after labels are removed
 */
function removeProcessLabels(ownerUsername, callback) {
  var expiredLabel = LABEL_PREFIX_EXPIRED + ownerUsername;
  var ticketLabelPrefix = LABEL_PREFIX_TICKET + ownerUsername + '_';
  var labels = AJS.Labels.getLabels() || [];

  var labelsToRemove = [];
  labels.forEach(function(label) {
    if (label.name === expiredLabel ||
        (label.name && label.name.indexOf(ticketLabelPrefix) === 0)) {
      labelsToRemove.push(label.name);
    }
  });

  var removed = 0;
  if (labelsToRemove.length === 0) {
    if (callback) callback();
    return;
  }

  labelsToRemove.forEach(function(labelName) {
    AJS.Labels.removeLabel(labelName, function() {
      console.log('[Maptimize] Removed label:', labelName);
      removed++;
      if (removed === labelsToRemove.length && callback) {
        callback();
      }
    });
  });
}

/**
 * Create a JIRA ticket for an expired process
 * @param {string} processId - The process ID from data-process-id attribute
 * @param {string} ownerUsername - The owner's username for assignee and label
 * @param {string} responsibility - The process responsibility description
 * @param {function} onSuccess - Callback with ticketKey on successful creation
 * @param {function} onError - Optional callback on error
 */
function createJiraTicket(processId, ownerUsername, responsibility, onSuccess, onError) {
  // Check for duplicate using Confluence labels
  if (hasProcessLabel(ownerUsername)) {
    var existingKey = getTicketKeyFromLabel(ownerUsername);
    console.log('[Maptimize] Ticket already exists for', ownerUsername, existingKey ? '(' + existingKey + ')' : '');
    if (onError) onError('Ticket already exists for this process owner');
    return;
  }

  // Get page title for context
  var pageTitle = AJS.$('#title-text').text() || document.title || 'Process Review';

  // Build JIRA ticket payload
  var summary = 'Review Process: ' + responsibility + ' - ' + pageTitle;
  var description = [
    'This process review has expired and requires attention.',
    '',
    'Process Owner: ' + ownerUsername,
    'Responsibility: ' + responsibility,
    'Process ID: ' + processId,
    'Page: ' + window.location.href,
    '',
    'Please review and update the process documentation.',
    '',
    '_Created automatically by Maptimize Timer_'
  ].join('\n');

  var payload = {
    fields: {
      project: {
        key: JIRA_PROJECT_KEY
      },
      issuetype: {
        name: JIRA_ISSUE_TYPE
      },
      summary: summary,
      description: description,
      assignee: {
        name: ownerUsername
      }
    }
  };

  // Create XHR request
  var xhr = new XMLHttpRequest();
  xhr.open('POST', JIRA_API_ENDPOINT, true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.setRequestHeader('Accept', 'application/json');

  xhr.onload = function() {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var response = JSON.parse(xhr.responseText);
        // API returns: {"issues": [{"key": "CPGNCX-63500", ...}]}
        var ticketKey = response.issues && response.issues[0] && response.issues[0].key;

        if (ticketKey) {
          console.log('[Maptimize] Created JIRA ticket:', ticketKey);

          // Add expired label first, then store ticket key
          addProcessLabel(ownerUsername, function() {
            storeTicketKeyLabel(ownerUsername, ticketKey, function() {
              if (onSuccess) onSuccess(ticketKey);
            });
          });
        } else {
          console.error('[Maptimize] No ticket key in response:', response);
          if (onError) onError('No ticket key returned from JIRA API');
        }
      } catch (e) {
        console.error('[Maptimize] Failed to parse JIRA response:', e);
        if (onError) onError('Failed to parse JIRA response');
      }
    } else {
      console.error('[Maptimize] JIRA API error:', xhr.status, xhr.statusText);
      if (onError) onError('JIRA API returned status ' + xhr.status);
    }
  };

  xhr.onerror = function() {
    console.error('[Maptimize] Network error creating JIRA ticket');
    if (onError) onError('Network error connecting to JIRA API');
  };

  xhr.send(JSON.stringify(payload));
}

/**
 * Process all expired rows and create JIRA tickets
 * Called after timer initialization to handle expired processes
 */
function processExpiredRows() {
  $('tr[data-process-id]').each(function() {
    var $row = $(this);
    var $expirySpan = $row.find('.process-expiry');

    // Check if row is expired
    if (!$expirySpan.hasClass('expired')) {
      return; // Skip non-expired rows
    }

    var processId = $row.data('process-id');
    var ownerUsername = $row.data('owner-username');
    var responsibility = $row.data('responsibility');

    if (!processId || !ownerUsername || !responsibility) {
      console.warn('[Maptimize] Missing required data attributes on row:', $row);
      return;
    }

    // Check if ticket already exists (from labels)
    var existingTicketKey = getTicketKeyFromLabel(ownerUsername);
    if (existingTicketKey || hasProcessLabel(ownerUsername)) {
      // Show existing ticket info
      if (existingTicketKey) {
        var ticketUrl = 'https://jira.corp.adobe.com/browse/' + existingTicketKey;
        $expirySpan.html('EXPIRED <a href="' + ticketUrl + '" target="_blank">' + existingTicketKey + '</a>');
      }
      return;
    }

    // Create JIRA ticket for this expired process
    createJiraTicket(processId, ownerUsername, responsibility,
      function(ticketKey) {
        // Success: Update display with ticket link
        var ticketUrl = 'https://jira.corp.adobe.com/browse/' + ticketKey;
        $expirySpan.html('EXPIRED <a href="' + ticketUrl + '" target="_blank">' + ticketKey + '</a>');
      },
      function(error) {
        // Error: Log and continue
        console.error('[Maptimize] Failed to create ticket for', ownerUsername, ':', error);
      }
    );
  });
}

// Export functions for external use and testing
if (typeof window !== 'undefined') {
  window.MaptimizeJira = {
    createJiraTicket: createJiraTicket,
    hasProcessLabel: hasProcessLabel,
    addProcessLabel: addProcessLabel,
    storeTicketKeyLabel: storeTicketKeyLabel,
    getTicketKeyFromLabel: getTicketKeyFromLabel,
    removeProcessLabels: removeProcessLabels,
    processExpiredRows: processExpiredRows
  };
}

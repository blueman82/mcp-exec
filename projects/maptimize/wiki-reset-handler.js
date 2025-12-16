/**
 * Reset Handler for Process Owner Timers
 * Handles reset button clicks with JIRA status category check and page update
 * Uses Confluence REST API to update page content and AUI dialogs for user feedback
 *
 * IMPORTANT: ES5 syntax required for Confluence compatibility
 * - Use var instead of const/let
 * - Use function() instead of arrow functions
 */

// JIRA integration API endpoint for getting ticket details
var JIRA_INTEGRATION_API = 'https://wiki.corp.adobe.com/rest/jira-integration/1.0/issues/';

// Confluence REST API base URL
var CONFLUENCE_API_BASE = 'https://wiki.corp.adobe.com/rest/api/content/';

// 90-day cycle in milliseconds (for calculating next due date)
var CYCLE_DAYS = 90;

/**
 * Get the current Confluence page ID from the URL or AJS.params
 * @returns {string|null} - The page ID or null if not found
 */
function getPageId() {
  // Try AJS.params first (most reliable in Confluence)
  if (typeof AJS !== 'undefined' && AJS.params && AJS.params.pageId) {
    return AJS.params.pageId;
  }
  // Fallback: extract from URL
  var match = window.location.pathname.match(/\/pages\/(\d+)\//);
  if (match) {
    return match[1];
  }
  return null;
}

/**
 * Fetch JIRA ticket status using the Confluence JIRA integration API
 * @param {string} ticketKey - The JIRA ticket key (e.g., 'CPGNCX-63500')
 * @param {function} onSuccess - Callback with ticket data including statusCategory
 * @param {function} onError - Callback on error with error message
 */
function checkJiraStatusCategory(ticketKey, onSuccess, onError) {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', JIRA_INTEGRATION_API + ticketKey, true);
  xhr.setRequestHeader('Accept', 'application/json');

  xhr.onload = function() {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var response = JSON.parse(xhr.responseText);
        // API returns issue details including status and statusCategory
        // Structure: { key: "CPGNCX-63500", fields: { status: { name: "Closed", statusCategory: { key: "done" } } } }
        if (response && response.fields && response.fields.status) {
          var status = response.fields.status;
          var statusCategory = status.statusCategory || {};
          onSuccess({
            ticketKey: ticketKey,
            statusName: status.name,
            statusCategoryKey: statusCategory.key || 'unknown',
            statusCategoryName: statusCategory.name || 'Unknown'
          });
        } else {
          console.error('[Maptimize] Invalid JIRA response structure:', response);
          onError('Unable to retrieve ticket status');
        }
      } catch (e) {
        console.error('[Maptimize] Failed to parse JIRA response:', e);
        onError('Failed to parse JIRA response');
      }
    } else {
      console.error('[Maptimize] JIRA API error:', xhr.status, xhr.statusText);
      onError('JIRA API returned status ' + xhr.status);
    }
  };

  xhr.onerror = function() {
    console.error('[Maptimize] Network error fetching JIRA ticket');
    onError('Network error connecting to JIRA API');
  };

  xhr.send();
}

/**
 * Display an AUI modal dialog with a message
 * @param {string} title - Dialog title
 * @param {string} message - Dialog message body
 * @param {string} type - Dialog type: 'error' or 'success'
 */
function showModal(title, message, type) {
  // Use AUI dialog2 if available (Confluence 5.5+)
  if (typeof AJS !== 'undefined' && AJS.dialog2) {
    var dialogId = 'maptimize-modal-' + Date.now();
    var iconClass = type === 'success' ? 'aui-iconfont-approve' : 'aui-iconfont-error';
    var headerClass = type === 'success' ? 'aui-dialog2-header' : 'aui-dialog2-header aui-dialog2-warning';

    var dialogHtml = [
      '<section id="' + dialogId + '" class="aui-dialog2 aui-dialog2-medium aui-layer" role="dialog" aria-modal="true">',
      '  <header class="' + headerClass + '">',
      '    <h2 class="aui-dialog2-header-main">' + title + '</h2>',
      '    <a class="aui-dialog2-header-close"><span class="aui-icon aui-icon-small aui-iconfont-close-dialog">Close</span></a>',
      '  </header>',
      '  <div class="aui-dialog2-content">',
      '    <p>' + message + '</p>',
      '  </div>',
      '  <footer class="aui-dialog2-footer">',
      '    <div class="aui-dialog2-footer-actions">',
      '      <button class="aui-button aui-button-primary maptimize-modal-close">OK</button>',
      '    </div>',
      '  </footer>',
      '</section>'
    ].join('\n');

    $('body').append(dialogHtml);

    var $dialog = $('#' + dialogId);
    var dialog = AJS.dialog2($dialog);

    // Bind close handlers
    $dialog.find('.aui-dialog2-header-close, .maptimize-modal-close').on('click', function() {
      dialog.hide();
      $dialog.remove();
    });

    dialog.show();
  } else {
    // Fallback to native alert
    alert(title + '\n\n' + message);
  }
}

/**
 * Update the Last Reviewed date on the Confluence page
 * @param {string} ownerUsername - The owner's username to identify the row
 * @param {function} onSuccess - Callback with new date on success
 * @param {function} onError - Callback on error with error message
 */
function updateLastReviewedDate(ownerUsername, onSuccess, onError) {
  var pageId = getPageId();
  if (!pageId) {
    onError('Could not determine page ID');
    return;
  }

  // Get current page content
  var xhr = new XMLHttpRequest();
  xhr.open('GET', CONFLUENCE_API_BASE + pageId + '?expand=body.storage,version', true);
  xhr.setRequestHeader('Accept', 'application/json');

  xhr.onload = function() {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var pageData = JSON.parse(xhr.responseText);
        var currentContent = pageData.body.storage.value;
        var currentVersion = pageData.version.number;

        // Parse HTML and find the row for this owner
        var $tempDiv = $('<div>').html(currentContent);
        var $targetRow = $tempDiv.find('tr[data-owner-username="' + ownerUsername + '"]');

        if ($targetRow.length === 0) {
          onError('Could not find row for user ' + ownerUsername);
          return;
        }

        // Update the <time> element's datetime attribute to today's date
        var today = new Date();
        var todayISO = today.toISOString().split('T')[0]; // YYYY-MM-DD format
        var todayFormatted = today.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

        var $timeElement = $targetRow.find('time[datetime]');
        if ($timeElement.length === 0) {
          onError('Could not find time element in row');
          return;
        }

        $timeElement.attr('datetime', todayISO);
        $timeElement.text(todayFormatted);

        // Get updated content
        var updatedContent = $tempDiv.html();

        // PUT updated content back to Confluence
        var updateXhr = new XMLHttpRequest();
        updateXhr.open('PUT', CONFLUENCE_API_BASE + pageId, true);
        updateXhr.setRequestHeader('Content-Type', 'application/json');
        updateXhr.setRequestHeader('Accept', 'application/json');

        var updatePayload = {
          id: pageId,
          type: 'page',
          title: pageData.title,
          body: {
            storage: {
              value: updatedContent,
              representation: 'storage'
            }
          },
          version: {
            number: currentVersion + 1
          }
        };

        updateXhr.onload = function() {
          if (updateXhr.status >= 200 && updateXhr.status < 300) {
            console.log('[Maptimize] Successfully updated page content');
            onSuccess(todayISO);
          } else {
            console.error('[Maptimize] Failed to update page:', updateXhr.status, updateXhr.statusText);
            onError('Failed to update page: ' + updateXhr.status);
          }
        };

        updateXhr.onerror = function() {
          console.error('[Maptimize] Network error updating page');
          onError('Network error updating page');
        };

        updateXhr.send(JSON.stringify(updatePayload));

      } catch (e) {
        console.error('[Maptimize] Failed to process page content:', e);
        onError('Failed to process page content');
      }
    } else {
      console.error('[Maptimize] Failed to get page content:', xhr.status);
      onError('Failed to get page content: ' + xhr.status);
    }
  };

  xhr.onerror = function() {
    console.error('[Maptimize] Network error getting page content');
    onError('Network error getting page content');
  };

  xhr.send();
}

/**
 * Calculate the next due date from today
 * @param {string} todayISO - Today's date in YYYY-MM-DD format
 * @returns {string} - Next due date in human-readable format
 */
function calculateNextDueDate(todayISO) {
  var today = new Date(todayISO);
  var nextDue = new Date(today.getTime() + (CYCLE_DAYS * 24 * 60 * 60 * 1000));
  return nextDue.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/**
 * Handle reset button click
 * @param {Event} event - Click event from the reset button
 */
function handleResetClick(event) {
  var $button = $(event.target);
  var processId = $button.data('process-id');
  var ownerUsername = $button.data('owner-username');

  if (!processId || !ownerUsername) {
    console.error('[Maptimize] Missing data attributes on reset button');
    showModal('Reset Error', 'Missing required data attributes on button', 'error');
    return;
  }

  // Get ticket key from labels
  var ticketKey = null;
  if (typeof window !== 'undefined' && window.MaptimizeJira && window.MaptimizeJira.getTicketKeyFromLabel) {
    ticketKey = window.MaptimizeJira.getTicketKeyFromLabel(ownerUsername);
  }

  if (!ticketKey) {
    console.error('[Maptimize] No ticket key found for', ownerUsername);
    showModal('Reset Error', 'No JIRA ticket found for this process. Cannot reset without a ticket.', 'error');
    return;
  }

  // Disable button during processing
  $button.prop('disabled', true).text('Checking...');

  // Check JIRA ticket status category
  checkJiraStatusCategory(ticketKey, function(statusData) {
    // Check if status category is 'done'
    if (statusData.statusCategoryKey !== 'done') {
      // Reset blocked - show error modal
      $button.prop('disabled', false).text('RESET');
      showModal(
        'Cannot Reset Timer',
        ticketKey + ' must be completed. Current status: ' + statusData.statusName,
        'error'
      );
      return;
    }

    // Status is done - proceed with reset
    $button.text('Updating...');

    // Update page content with new Last Reviewed date
    updateLastReviewedDate(ownerUsername, function(todayISO) {
      // Remove labels
      if (window.MaptimizeJira && window.MaptimizeJira.removeProcessLabels) {
        window.MaptimizeJira.removeProcessLabels(ownerUsername, function() {
          // Calculate next due date for success message
          var nextDueDate = calculateNextDueDate(todayISO);
          var todayFormatted = new Date(todayISO).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

          // Show success modal
          showModal(
            'Timer Reset Successfully',
            'Last Reviewed: ' + todayFormatted + '\nNext due: ' + nextDueDate,
            'success'
          );

          // Refresh the page to update all displays
          // Use a short delay to allow modal to be seen
          setTimeout(function() {
            location.reload();
          }, 2000);
        });
      } else {
        // Labels module not available, still show success
        var nextDueDate = calculateNextDueDate(todayISO);
        var todayFormatted = new Date(todayISO).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

        showModal(
          'Timer Reset Successfully',
          'Last Reviewed: ' + todayFormatted + '\nNext due: ' + nextDueDate,
          'success'
        );

        setTimeout(function() {
          location.reload();
        }, 2000);
      }
    }, function(error) {
      $button.prop('disabled', false).text('RESET');
      showModal('Reset Error', 'Failed to update page: ' + error, 'error');
    });

  }, function(error) {
    $button.prop('disabled', false).text('RESET');
    showModal('Reset Error', 'Failed to check JIRA ticket status: ' + error, 'error');
  });
}

/**
 * Initialize reset button handlers using event delegation
 * Should be called once when the page loads
 */
function initializeResetHandlers() {
  // Use event delegation for dynamically added buttons
  $(document).on('click', '.reset-timer-btn', handleResetClick);
  console.log('[Maptimize] Reset handlers initialized');
}

// Initialize when DOM is ready
$(document).ready(function() {
  initializeResetHandlers();
});

// Export functions for external use and testing
if (typeof window !== 'undefined') {
  window.MaptimizeReset = {
    handleResetClick: handleResetClick,
    checkJiraStatusCategory: checkJiraStatusCategory,
    showModal: showModal,
    updateLastReviewedDate: updateLastReviewedDate,
    initializeResetHandlers: initializeResetHandlers,
    getPageId: getPageId,
    calculateNextDueDate: calculateNextDueDate
  };
}

/**
 * Process Owners Timer Script
 * Calculates and displays 90-day countdown timers for process review cycles
 * Designed for Confluence wiki integration via HTML macro
 *
 * IMPORTANT: ES5 syntax required for Confluence compatibility
 * - Use var instead of const/let
 * - Use function() instead of arrow functions
 */

// 90-day review cycle in milliseconds
var CYCLE_MS = 90 * 24 * 60 * 60 * 1000; // 7776000000 ms

/**
 * Pure function to calculate countdown from last review date
 * @param {number} lastReviewTimestamp - Unix timestamp of last review date
 * @returns {Object} - {days: number, hours: number, expired: boolean}
 */
function calculateCountdown(lastReviewTimestamp) {
  var now = Date.now();
  var expiryTimestamp = lastReviewTimestamp + CYCLE_MS;
  var distance = expiryTimestamp - now;

  if (distance <= 0) {
    return { days: 0, hours: 0, expired: true };
  }

  var days = Math.floor(distance / (24 * 60 * 60 * 1000));
  var hours = Math.floor((distance % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));

  return { days: days, hours: hours, expired: false };
}

/**
 * Format countdown result for display
 * @param {Object} countdown - Result from calculateCountdown
 * @returns {string} - Formatted display string
 */
function formatCountdown(countdown) {
  if (countdown.expired) {
    return 'EXPIRED';
  }
  return countdown.days + ' days ' + countdown.hours + ' hours';
}

/**
 * Initialize timers for all process owner rows
 * Iterates through rows with data-process-id attribute
 */
function initializeProcessTimers() {
  $('tr[data-process-id]').each(function() {
    var $row = $(this);
    var $timeElement = $row.find('time[datetime]');
    var $expirySpan = $row.find('.process-expiry');

    if ($timeElement.length === 0 || $expirySpan.length === 0) {
      return; // Skip rows without required elements
    }

    var datetimeStr = $timeElement.attr('datetime');
    var lastReviewDate = new Date(datetimeStr);
    var lastReviewTimestamp = lastReviewDate.getTime();

    if (isNaN(lastReviewTimestamp)) {
      $expirySpan.text('Invalid date');
      return;
    }

    var countdown = calculateCountdown(lastReviewTimestamp);
    var displayText = formatCountdown(countdown);

    $expirySpan.text(displayText);

    if (countdown.expired) {
      $expirySpan.addClass('expired');
    } else {
      $expirySpan.removeClass('expired');
    }
  });
}

// Initialize when DOM is ready
$(document).ready(function() {
  initializeProcessTimers();
});

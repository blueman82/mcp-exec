/**
 * Simple validation test for Phase 3 Search Context Enhancement
 * Tests core functionality without dependency issues
 */

// Mock DOM environment
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>');
global.window = dom.window;
global.document = dom.window.document;
global.localStorage = {
  data: {},
  getItem: function(key) { return this.data[key] || null; },
  setItem: function(key, value) { this.data[key] = value; },
  removeItem: function(key) { delete this.data[key]; },
  clear: function() { this.data = {}; }
};

// Load modules using dynamic import
async function runValidation() {
  console.log('🔍 Starting Phase 3 Search Context Enhancement Validation\n');

  try {
    // Import modules
    console.log('📦 Loading modules...');
    const { createSearchHighlighter } = await import('./lib/search-highlighter.ts');
    const { createSearchGrouper } = await import('./lib/search-grouper.ts');

    // Create mock search result
    const mockSearchResult = {
      query: 'error',
      matches: [
        {
          lineIndex: 0,
          log: {
            timestamp: '2023-01-01T12:00:00Z',
            content: 'Database connection error occurred',
            container: 'ketchup-app',
            server: 'prod1',
            level: 'error',
          },
          matchStart: 20,
          matchEnd: 25,
          score: 150,
          context: 'connection error',
        },
        {
          lineIndex: 1,
          log: {
            timestamp: '2023-01-01T12:05:00Z',
            content: 'API timeout warning',
            container: 'ketchup-app',
            server: 'prod2',
            level: 'warn',
          },
          matchStart: 0,
          matchEnd: 0,
          score: 80,
          context: 'API timeout',
        },
        {
          lineIndex: 2,
          log: {
            timestamp: '2023-01-01T11:30:00Z',
            content: 'Authentication failed error',
            container: 'ketchup-auth',
            server: 'prod1',
            level: 'error',
          },
          matchStart: 20,
          matchEnd: 25,
          score: 120,
          context: 'failed error',
        },
      ],
      totalMatches: 3,
      executionTime: 15,
      filters: {},
      searchMode: 'text',
      hasMore: false,
    };

    let passedTests = 0;
    let totalTests = 0;

    // Test 1: Search Highlighter Creation and Initialization
    console.log('\n🎨 Test 1: Search Highlighter Initialization');
    totalTests++;
    try {
      const highlighter = createSearchHighlighter({
        theme: 'light',
        enableAnimations: false,
        contextRadius: 20,
        maxHighlights: 100,
      });

      if (highlighter && typeof highlighter.processSearchResults === 'function') {
        console.log('✅ SearchHighlighter created successfully');
        passedTests++;
      } else {
        console.log('❌ SearchHighlighter creation failed');
      }
    } catch (error) {
      console.log('❌ SearchHighlighter creation error:', error.message);
    }

    // Test 2: Search Highlighter Processing
    console.log('\n🎯 Test 2: Search Highlighter Processing');
    totalTests++;
    try {
      const highlighter = createSearchHighlighter({ theme: 'light' });
      const highlights = highlighter.processSearchResults(mockSearchResult);

      if (Array.isArray(highlights) && highlights.length > 0) {
        console.log(`✅ Processed ${highlights.length} highlights successfully`);
        console.log(`   Primary highlights: ${highlights.filter(h => h.type === 'primary').length}`);
        console.log(`   Context highlights: ${highlights.filter(h => h.type === 'context').length}`);
        passedTests++;
      } else {
        console.log('❌ Highlight processing failed or returned empty array');
      }
    } catch (error) {
      console.log('❌ Highlight processing error:', error.message);
    }

    // Test 3: Search Highlighter Navigation
    console.log('\n🔀 Test 3: Search Highlighter Navigation');
    totalTests++;
    try {
      const highlighter = createSearchHighlighter({ theme: 'light' });
      highlighter.processSearchResults(mockSearchResult);
      const navigation = highlighter.getNavigationState();

      if (navigation && typeof navigation.total === 'number' && navigation.total > 0) {
        console.log(`✅ Navigation state: ${navigation.current + 1}/${navigation.total} highlights`);

        // Test navigation
        highlighter.navigateToNext();
        const afterNext = highlighter.getNavigationState();
        highlighter.navigateToPrevious();
        const afterPrev = highlighter.getNavigationState();

        console.log(`✅ Navigation works: next(${afterNext.current}), prev(${afterPrev.current})`);
        passedTests++;
      } else {
        console.log('❌ Navigation state invalid');
      }
    } catch (error) {
      console.log('❌ Navigation error:', error.message);
    }

    // Test 4: Search Grouper Creation and Initialization
    console.log('\n📊 Test 4: Search Grouper Initialization');
    totalTests++;
    try {
      const grouper = createSearchGrouper({
        grouping: { groupBy: 'container' },
        sorting: { sortBy: 'relevance' },
        persistPreferences: false,
      });

      if (grouper && typeof grouper.processSearchResult === 'function') {
        console.log('✅ SearchGrouper created successfully');
        passedTests++;
      } else {
        console.log('❌ SearchGrouper creation failed');
      }
    } catch (error) {
      console.log('❌ SearchGrouper creation error:', error.message);
    }

    // Test 5: Search Grouper Processing
    console.log('\n🗂️ Test 5: Search Grouper Processing');
    totalTests++;
    try {
      const grouper = createSearchGrouper({ groupBy: 'container' });
      const grouped = grouper.processSearchResult(mockSearchResult);

      if (grouped && grouped.groups && grouped.groups.size > 0) {
        console.log(`✅ Grouped results into ${grouped.groups.size} groups:`);
        for (const [groupKey, groupInfo] of grouped.groups.entries()) {
          console.log(`   ${groupKey}: ${groupInfo.count} matches`);
        }
        console.log(`✅ Sorted ${grouped.sortedMatches.length} matches`);
        passedTests++;
      } else {
        console.log('❌ Grouping failed or returned empty groups');
      }
    } catch (error) {
      console.log('❌ Grouping error:', error.message);
    }

    // Test 6: Multiple Grouping Options
    console.log('\n🔄 Test 6: Multiple Grouping Options');
    totalTests++;
    try {
      const grouper = createSearchGrouper();
      const groupingOptions = ['container', 'server', 'logLevel', 'none'];
      const results = {};

      for (const option of groupingOptions) {
        grouper.updateGroupingConfig({ groupBy: option });
        const grouped = grouper.processSearchResult(mockSearchResult);
        results[option] = grouped.groups.size;
      }

      console.log('✅ Grouping results:');
      for (const [option, count] of Object.entries(results)) {
        console.log(`   ${option}: ${count} groups`);
      }

      if (results.container > 0 && results.server > 0 && results.logLevel > 0) {
        console.log('✅ Multiple grouping options work correctly');
        passedTests++;
      } else {
        console.log('❌ Some grouping options failed');
      }
    } catch (error) {
      console.log('❌ Grouping options error:', error.message);
    }

    // Test 7: Sorting Options
    console.log('\n⬆️ Test 7: Sorting Options');
    totalTests++;
    try {
      const grouper = createSearchGrouper();
      const sortingOptions = ['relevance', 'mostRecent', 'leastRecent', 'logLevelPriority'];
      const results = {};

      for (const option of sortingOptions) {
        grouper.updateSortingConfig({ sortBy: option });
        const grouped = grouper.processSearchResult(mockSearchResult);
        results[option] = grouped.sortedMatches.map(m => m.score);
      }

      console.log('✅ Sorting results (scores shown):');
      for (const [option, scores] of Object.entries(results)) {
        console.log(`   ${option}: [${scores.join(', ')}]`);
      }

      // Check if relevance sorting is descending (highest scores first)
      const relevanceScores = results.relevance;
      if (relevanceScores[0] >= relevanceScores[1] && relevanceScores[1] >= relevanceScores[2]) {
        console.log('✅ Relevance sorting works correctly (descending)');
        passedTests++;
      } else {
        console.log('❌ Relevance sorting not working correctly');
      }
    } catch (error) {
      console.log('❌ Sorting options error:', error.message);
    }

    // Test 8: Theme Support
    console.log('\n🎨 Test 8: Theme Support');
    totalTests++;
    try {
      const highlighter = createSearchHighlighter({ theme: 'light' });
      highlighter.processSearchResults(mockSearchResult);
      const lightHighlights = highlighter.getHighlights();

      highlighter.updateTheme('dark');
      const darkHighlights = highlighter.getHighlights();

      if (lightHighlights.length > 0 && darkHighlights.length > 0) {
        const lightClasses = lightHighlights[0].className;
        const darkClasses = darkHighlights[0].className;

        if (lightClasses !== darkClasses) {
          console.log('✅ Theme switching works correctly');
          console.log(`   Light theme classes: ${lightClasses}`);
          console.log(`   Dark theme classes: ${darkClasses}`);
          passedTests++;
        } else {
          console.log('❌ Theme switching did not update classes');
        }
      } else {
        console.log('❌ No highlights generated for theme testing');
      }
    } catch (error) {
      console.log('❌ Theme support error:', error.message);
    }

    // Test 9: Performance with Large Dataset
    console.log('\n⚡ Test 9: Performance with Large Dataset');
    totalTests++;
    try {
      const largeResult = {
        query: 'test',
        matches: Array.from({ length: 500 }, (_, i) => ({
          lineIndex: i,
          log: {
            timestamp: new Date(Date.now() - i * 1000).toISOString(),
            content: `Test message ${i} with error details`,
            container: `ketchup-${i % 5}`,
            server: i % 2 === 0 ? 'prod1' : 'prod2',
            level: ['error', 'warn', 'info', 'debug'][i % 4],
          },
          matchStart: 15,
          matchEnd: 19,
          score: 100 - (i * 0.1),
          context: 'Test message',
        })),
        totalMatches: 500,
        executionTime: 100,
        filters: {},
        searchMode: 'text',
        hasMore: false,
      };

      // Test highlighter performance
      const startTime1 = performance.now();
      const highlighter = createSearchHighlighter({ theme: 'light' });
      const highlights = highlighter.processSearchResults(largeResult);
      const endTime1 = performance.now();
      const highlightTime = endTime1 - startTime1;

      // Test grouper performance
      const startTime2 = performance.now();
      const grouper = createSearchGrouper({ groupBy: 'container' });
      const grouped = grouper.processSearchResult(largeResult);
      const endTime2 = performance.now();
      const groupTime = endTime2 - startTime2;

      console.log(`✅ Performance results for 500 matches:`);
      console.log(`   Highlighter: ${highlightTime.toFixed(2)}ms (${highlights.length} highlights)`);
      console.log(`   Grouper: ${groupTime.toFixed(2)}ms (${grouped.groups.size} groups)`);

      if (highlightTime < 1000 && groupTime < 500) {
        console.log('✅ Performance targets met');
        passedTests++;
      } else {
        console.log('❌ Performance targets not met');
      }
    } catch (error) {
      console.log('❌ Performance test error:', error.message);
    }

    // Test 10: DOM Highlight Application
    console.log('\n🌐 Test 10: DOM Highlight Application');
    totalTests++;
    try {
      const highlighter = createSearchHighlighter({ theme: 'light' });
      const container = document.createElement('div');
      container.innerHTML = 'Database connection error occurred - API timeout warning';

      highlighter.processSearchResults(mockSearchResult);
      highlighter.applyHighlights(container);

      const highlightedElements = container.querySelectorAll('[data-highlight-id]');
      if (highlightedElements.length > 0) {
        console.log(`✅ Applied ${highlightedElements.length} highlight elements to DOM`);
        highlightedElements.forEach((el, i) => {
          console.log(`   Element ${i + 1}: ${el.outerHTML.substring(0, 100)}...`);
        });
        passedTests++;
      } else {
        console.log('❌ No highlight elements applied to DOM');
      }
    } catch (error) {
      console.log('❌ DOM highlight application error:', error.message);
    }

    // Summary
    console.log('\n📋 VALIDATION SUMMARY');
    console.log('=====================================');
    console.log(`Tests Passed: ${passedTests}/${totalTests}`);
    console.log(`Success Rate: ${((passedTests / totalTests) * 100).toFixed(1)}%`);

    if (passedTests === totalTests) {
      console.log('🎉 ALL TESTS PASSED! Phase 3 implementation is working correctly.');
    } else if (passedTests >= totalTests * 0.8) {
      console.log('✅ MAJORITY OF TESTS PASSED! Phase 3 implementation is mostly working.');
    } else {
      console.log('⚠️  SEVERAL TESTS FAILED! Phase 3 implementation needs attention.');
    }

    return passedTests === totalTests;

  } catch (error) {
    console.error('❌ Validation failed with error:', error);
    return false;
  }
}

// Run validation if called directly
if (require.main === module) {
  runValidation().then(success => {
    process.exit(success ? 0 : 1);
  }).catch(error => {
    console.error('Validation script failed:', error);
    process.exit(1);
  });
}

module.exports = { runValidation };
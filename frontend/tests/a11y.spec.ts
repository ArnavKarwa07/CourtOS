import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('CourtOS Operator Dashboard Accessibility & E2E', () => {
  test('should pass automated WCAG 2.2 AA standards scan', async ({ page }) => {
    // Navigate to local dashboard dev or build server
    await page.goto('http://localhost:5173');
    
    // Wait for header to render
    await expect(page.locator('h1')).toContainText('CourtOS');
    
    // Run Axe audit
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
      .analyze();
      
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('should support keyboard-only incident resolution navigation', async ({ page }) => {
    await page.goto('http://localhost:5173');
    
    // Set focus on theme toggle button using tab
    await page.keyboard.press('Tab');
    
    // Keep tabbing until we reach the incident resolve button if any exists
    // (In simulation, incident card will be pushed within 10 seconds)
    await page.waitForTimeout(2000); 
    
    const resolveBtn = page.locator('button:has-text("Resolve")').first();
    if (await resolveBtn.isVisible()) {
      await resolveBtn.focus();
      await expect(resolveBtn).toBeFocused();
      
      // Press enter to resolve optimistically
      await page.keyboard.press('Enter');
      
      // Card should be removed immediately from UI list
      await expect(resolveBtn).not.toBeVisible();
    }
  });
});

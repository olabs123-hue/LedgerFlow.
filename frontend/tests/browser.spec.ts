import { test, expect } from '@playwright/test';

test('register, sign in, fund a demo account, transfer and check history', async ({ page }) => {
  const suffix = Date.now().toString(36);
  const alice = `alice-${suffix}@example.com`;
  const bob = `bob-${suffix}@example.com`;
  const password = 'portfolio-demo-password-123';

  async function register(email: string) {
    await page.getByRole('button', { name: 'New here? Create an account' }).click();
    await page.getByRole('textbox', { name: 'Email address' }).fill(email);
    await page.getByLabel('Password').fill(password);
    await page.getByRole('button', { name: 'Create account' }).click();
    await expect(page.getByText('Account created. Sign in to continue.')).toBeVisible();
  }

  async function signIn(email: string) {
    await page.getByRole('textbox', { name: 'Email address' }).fill(email);
    await page.getByLabel('Password').fill(password);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Financial overview' })).toBeVisible();
  }

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome to LedgerFlow' })).toBeVisible();
  await register(bob);
  await signIn(bob);
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('heading', { name: 'Welcome to LedgerFlow' })).toBeVisible();

  await register(alice);
  await signIn(alice);
  await page.getByRole('button', { name: '+ $1,000 demo' }).click();
  await expect(page.getByText('Added $1,000 in fictional demo credits.')).toBeVisible();
  await expect(page.getByText('$1,000.00')).toBeVisible();

  await page.getByRole('textbox', { name: 'Recipient email' }).fill(bob);
  await page.getByRole('spinbutton', { name: 'Amount (USD demo)' }).fill('12.50');
  await page.getByRole('button', { name: 'Send demo transfer' }).click();
  await expect(page.getByText('Outgoing transfer')).toBeVisible();
  await expect(page.getByText('$987.50')).toBeVisible();
  await page.getByRole('button', { name: 'Sign out' }).click();

  await signIn(bob);
  await expect(page.getByText('Incoming transfer')).toBeVisible();
  await expect(page.getByText('$12.50')).toBeVisible();
});

test('mobile layout keeps login controls usable', async ({ page, isMobile }) => {
  if (!isMobile) return;
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome to LedgerFlow' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Email address' })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
  expect(overflow).toBe(false);
});

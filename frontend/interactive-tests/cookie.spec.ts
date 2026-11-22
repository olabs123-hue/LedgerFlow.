import {test, expect} from '@playwright/test';

test('HTTPS cookie-only UI: sign in, fictional transfer, sign out', async ({page, context})=>{
  await page.goto('/');
  await expect(page.getByRole('heading', {name:'LedgerFlow browser demo'})).toBeVisible();
  await expect(page.getByText('Sign in using a demo account.')).toBeVisible();
  await expect(page.getByText('Secure demonstration access')).toBeVisible();
  await page.getByLabel('Email').fill('ci-alice@example.org');
  await page.getByLabel('Password').fill('ci-password-only-not-for-real-users-123');
  await page.getByRole('button', {name:'Sign in'}).click();
  await expect(page.getByText('Simulated balance')).toBeVisible();
  await expect(page.getByText('$1,000.00')).toBeVisible();

  const allCookies = await context.cookies();
  const cookie = allCookies.find(item => item.name === '__Host-lf_session');
  expect(cookie).toBeDefined();
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.secure).toBe(true);
  expect(cookie?.sameSite).toBe('Strict');
  await expect.poll(async()=>page.evaluate(()=>window.sessionStorage.length)).toBe(0);

  await page.getByLabel('Recipient email').fill('ci-bob@example.org');
  await page.getByLabel('Amount (USD)').fill('12.50');
  await page.getByRole('button', {name:'Send simulated transfer'}).click();
  await expect(page.getByText('Fictional transfer recorded.')).toBeVisible();
  await expect(page.getByText('$987.50')).toBeVisible();
  await expect(page.getByText('$12.50')).toBeVisible();

  await page.getByRole('button', {name:'Sign out'}).click();
  await expect(page.getByRole('button', {name:'Sign in'})).toBeVisible();
  expect((await context.cookies()).some(item=>item.name === '__Host-lf_session')).toBe(false);
  await expect(page.getByText('Signed out of this browser.')).toBeVisible();
});

test('preflight and the old bearer login route remain inaccessible', async ({request})=>{
  const legacy=await request.post('/auth/login',{data:{email:'ci-alice@example.org',password:'invalid-only'}});
  expect(legacy.status()).toBe(404);
  const registration=await request.post('/auth/register',{data:{email:'someone@example.org',password:'invalid-only'}});
  expect(registration.status()).toBe(404);
  const credit=await request.post('/demo/credit',{data:{}});
  expect(credit.status()).toBe(404);
});

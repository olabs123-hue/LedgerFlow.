import {test,expect} from '@playwright/test';

test('mobile HTTPS cookie demo renders and manages a session', async({page,context})=>{
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'LedgerFlow browser demo'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Secure demonstration access'})).toBeVisible();
  await page.getByLabel('Email').fill('ci-alice@example.org');
  await page.getByLabel('Password').fill('ci-password-only-not-for-real-users-123');
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByText('Simulated balance')).toBeVisible();
  await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();
  const cookie=(await context.cookies()).find(cookie=>cookie.name==='__Host-lf_session');
  expect(cookie?.secure).toBe(true);
  expect(cookie?.httpOnly).toBe(true);
  await page.getByRole('button',{name:'Sign out'}).click();
  await expect(page.getByRole('button',{name:'Sign in'})).toBeVisible();
});

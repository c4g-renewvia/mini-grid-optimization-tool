export function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className='flex items-center justify-between border-t px-4 py-6'>
      <p className='text-sm'>© {currentYear} C4G. All rights reserved.</p>
    </footer>
  );
}

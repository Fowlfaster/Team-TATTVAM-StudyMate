export default function Logo({ className = '' }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg aria-hidden="true" className="h-10 w-10 shrink-0" fill="none" viewBox="0 0 44 44">
        <path d="M5.5 12.5c5.2-2.1 10.3-1.4 16.5 3.2v19c-6.2-4.6-11.3-5.3-16.5-3.2v-19Z" fill="#E8F0E6" stroke="#284E3C" strokeLinejoin="round" strokeWidth="2" />
        <path d="M38.5 12.5c-5.2-2.1-10.3-1.4-16.5 3.2v19c6.2-4.6 11.3-5.3 16.5-3.2v-19Z" fill="#F9E5D8" stroke="#284E3C" strokeLinejoin="round" strokeWidth="2" />
        <path d="M22 15.8v19" stroke="#284E3C" strokeLinecap="round" strokeWidth="1.8" />
        <path d="M31.8 5.1v5.2M29.2 7.7h5.2M35.4 11.7v3.2M33.8 13.3H37" stroke="#D87556" strokeLinecap="round" strokeWidth="1.8" />
      </svg>
      <span className="whitespace-nowrap text-[17px] font-bold tracking-normal text-[#29372f]">StudyMate <span className="font-medium text-[#386951]">AI</span></span>
    </span>
  )
}
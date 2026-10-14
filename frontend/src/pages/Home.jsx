import { ArrowDown, ArrowRight, BookOpenCheck, Brain, ChartNoAxesColumnIncreasing, CircleHelp, FileText, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import Logo from '../components/Logo'

const steps = [
  { number: '01', title: 'Upload', detail: 'Bring in your slides, notes, or recorded lectures.', icon: FileText },
  { number: '02', title: 'Choose how to learn', detail: 'Ask for an explanation or put your knowledge to the test.', icon: Sparkles },
  { number: '03', title: 'Track your understanding', detail: 'See what is sticking and what deserves another look.', icon: ChartNoAxesColumnIncreasing },
]

const features = [
  { title: 'Explanation', detail: 'Get clear, course-grounded answers in the style that works for you.', icon: BookOpenCheck, color: 'bg-[#e4eee3] text-[#386951]' },
  { title: 'Quiz', detail: 'Practice with questions that adapt as your understanding grows.', icon: CircleHelp, color: 'bg-[#f7e6da] text-[#a95c42]' },
  { title: 'Concept Evaluation', detail: 'Find out which ideas you know well and which need another pass.', icon: Brain, color: 'bg-[#e6ebf2] text-[#506884]' },
  { title: 'Understanding Ranking', detail: 'Follow your progress across the topics in your own material.', icon: ChartNoAxesColumnIncreasing, color: 'bg-[#f6edcf] text-[#927628]' },
]

export default function Home() {
  return (
    <div className="home-page">
      <header className="home-nav">
        <div className="home-nav-inner">
          <Link aria-label="StudyMate AI home" className="home-logo-link" to="/"><Logo /></Link>
          <nav aria-label="Account navigation" className="flex items-center gap-3 sm:gap-5">
            <Link className="px-2 py-2 text-sm font-semibold text-[#405047] transition-colors hover:text-[#a95c42]" to="/login">Log in</Link>
            <Link className="home-nav-cta" to="/signup">Sign up <ArrowRight size={15} /></Link>
          </nav>
        </div>
      </header>

      <main>
        <section aria-labelledby="hero-title" className="home-hero">
          <img alt="Open study notes and books on a sunlit desk" className="home-hero-image" src="https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?auto=format&fit=crop&w=2400&q=85" />
          <div aria-hidden="true" className="home-hero-shade" />
          <div className="home-hero-content">
            <span className="home-hero-eyebrow"><span /> A study space built around you</span>
            <h1 id="hero-title">Your course, your pace,<br /><em>your personal tutor.</em></h1>
            <p>Make your own course material the starting point for better questions, clearer explanations, and learning that lasts.</p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link className="home-primary-button" to="/signup">Get started free <ArrowRight size={17} /></Link>
              <a className="home-scroll-link" href="#how-it-works">See how it works <ArrowDown size={15} /></a>
            </div>
          </div>
          <div aria-hidden="true" className="home-hero-caption"><span>01</span> Learn from what you already have</div>
        </section>

        <section className="home-process" id="how-it-works">
          <div className="home-section-heading">
            <span className="home-kicker">A BETTER WAY TO STUDY</span>
            <h2>From course material<br className="hidden sm:block" /> to real understanding.</h2>
            <p>Everything starts with your material. StudyMate helps you take it from there.</p>
          </div>
          <div className="home-steps">
            {steps.map(({ number, title, detail, icon: Icon }, index) => (
              <article className="home-step" key={number}>
                <div className="home-step-top"><span>{number}</span><Icon aria-hidden="true" size={21} strokeWidth={1.7} /></div>
                <h3>{title}</h3>
                <p>{detail}</p>
                {index < steps.length - 1 && <ArrowRight aria-hidden="true" className="home-step-arrow" size={21} />}
              </article>
            ))}
          </div>
        </section>

        <section className="home-features" id="features">
          <div className="home-features-head">
            <div>
              <span className="home-kicker">YOUR PERSONAL STUDY TOOLKIT</span>
              <h2>One course. Many ways in.</h2>
            </div>
            <p>Move between asking, practicing, and reflecting without losing sight of what you are learning.</p>
          </div>
          <div className="home-feature-grid">
            {features.map(({ title, detail, icon: Icon, color }, index) => (
              <article className="home-feature-card" key={title}>
                <div className={`home-feature-icon ${color}`}><Icon aria-hidden="true" size={21} strokeWidth={1.8} /></div>
                <span className="home-feature-index">0{index + 1}</span>
                <h3>{title}</h3>
                <p>{detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="home-citations">
          <div className="home-citation-copy">
            <span className="home-kicker home-kicker-light">GROUNDED IN YOUR MATERIAL</span>
            <h2>Every answer<br />is cited.</h2>
            <p>See where an explanation came from, then jump back into the source. Your notes stay in the conversation.</p>
          </div>
          <div className="home-citation-example">
            <div className="home-citation-top"><span className="home-citation-dot" /> SOURCE REFERENCE <span>01</span></div>
            <blockquote>“The main idea becomes clearer when we compare it with the example from lecture.”</blockquote>
            <div className="home-citation-source"><FileText aria-hidden="true" size={18} /><span><strong>Lecture notes.pdf</strong><small>Page 12 · Topic overview</small></span><ArrowRight aria-hidden="true" size={17} /></div>
          </div>
        </section>

        <section className="home-final-cta">
          <div className="home-final-mark"><Sparkles aria-hidden="true" size={19} /></div>
          <span className="home-kicker">YOUR NEXT STUDY SESSION STARTS HERE</span>
          <h2>Make your course<br className="sm:hidden" /> feel learnable.</h2>
          <p>Bring your material. We’ll help you find your next step.</p>
          <Link className="home-final-button" to="/signup">Get started free <ArrowRight size={17} /></Link>
        </section>
      </main>

      <footer className="home-footer">
        <Link aria-label="StudyMate AI home" className="home-logo-link" to="/"><Logo /></Link>
        <p>Learn it. Keep it. Own it.</p>
        <span>© 2026 STUDYMATE AI</span>
      </footer>
    </div>
  )
}
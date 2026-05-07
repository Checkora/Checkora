document.addEventListener('DOMContentLoaded', function(){
  // add loaded class for entry animations
  requestAnimationFrame(()=> document.documentElement.classList.add('loaded'));

  // Start Game animation then navigate
  const startBtn = document.querySelector('.primary');
  if(startBtn){
    startBtn.addEventListener('click', function(e){
      e.preventDefault();
      const isUnmodifiedPrimaryClick = e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
       if(!isUnmodifiedPrimaryClick){
         return;
       }
       e.preventDefault();
       const href = startBtn.getAttribute('href') || '/play/';
       if(typeof startBtn.animate === 'function'){
         startBtn.animate([
           { transform: 'scale(1)', opacity: 1 },
           { transform: 'scale(0.96)', opacity: 0.95 },
           { transform: 'scale(1)', opacity: 1 }
         ], { duration: 260, easing: 'cubic-bezier(.2,.8,.2,1)' });
       }
      setTimeout(()=> { window.location.href = href; }, 280);
    });
  }

  // smooth scrolling handled by CSS `scroll-behavior: smooth` but add a11y focus management
  document.querySelectorAll('a[href^="#"]').forEach(a=>{
    a.addEventListener('click', function(e){
      const target = document.querySelector(this.getAttribute('href'));
      if(target){
        e.preventDefault();
        target.scrollIntoView({behavior:'smooth', block:'start'});
        target.setAttribute('tabindex','-1');
        target.focus({preventScroll:true});
      }
    });
  });

  // Feature card flip: support click/touch and keyboard (Enter/Space)
  document.querySelectorAll('.feature-card').forEach(card=>{
    const inner = card.querySelector('.card-inner');
    if(!inner) return;

       function toggleFeatureCard(){
       const isFlipped = inner.classList.toggle('flipped');
       card.setAttribute('aria-pressed', String(isFlipped));
     }
     // keyboard-accessible toggle semantics
     card.setAttribute('tabindex', '0');
     card.setAttribute('role', 'button');
     card.setAttribute('aria-pressed', String(inner.classList.contains('flipped')));


    // toggle on click (for touch and mouse)
    card.addEventListener('click', function(e){
      // ignore if clicking a link inside
      if(e.target.closest('a')) return;
      toggleFeatureCard();
    });

    // keyboard support
    card.addEventListener('keydown', function(e){
      if(e.key === 'Enter' || e.key === ' '){
        e.preventDefault();
        toggleFeatureCard();
      }
    });
  });
});

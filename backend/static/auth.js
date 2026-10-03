// Native form validation remains active; passwords never enter browser storage.
for(const form of document.querySelectorAll('form')){
 form.addEventListener('submit',event=>{
  if(form.dataset.submitting){event.preventDefault();return}
  form.dataset.submitting='true';const button=form.querySelector('button[type=submit]');button.disabled=true;
  form.querySelector('.form-status').textContent=button.dataset.wait||'Envoi…';
 });
}
window.addEventListener('pageshow',()=>{for(const form of document.querySelectorAll('form')){delete form.dataset.submitting;form.querySelector('button[type=submit]').disabled=false;form.querySelector('.form-status').textContent=''}});

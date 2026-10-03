// ==========================================
// DATA SCIENCE PORTFOLIO - JAVASCRIPT
// ==========================================


// 1. Cuộn mượt khi bấm menu
document.querySelectorAll('a[href^="#"]').forEach(link => {

    link.addEventListener('click', function (event) {

        const targetId = this.getAttribute('href');
        const target = document.querySelector(targetId);

        if (target) {
            event.preventDefault();

            target.scrollIntoView({
                behavior: 'smooth'
            });
        }
    });

});


// 2. Hiệu ứng xuất hiện cho các project card
const cards = document.querySelectorAll('.project-card');

const observer = new IntersectionObserver((entries) => {

    entries.forEach(entry => {

        if (entry.isIntersecting) {
            entry.target.classList.add('show');
        }

    });

}, {
    threshold: 0.15
});

cards.forEach(card => {
    observer.observe(card);
});


// 3. Xử lý các nút chức năng
const buttons = document.querySelectorAll('.project-card button');

buttons.forEach(button => {

    button.addEventListener('click', function () {

        const projectName =
            this.parentElement.querySelector('h3').innerText;

        alert(
            projectName +
            '\n\nChức năng này đang được phát triển.'
        );

    });

});
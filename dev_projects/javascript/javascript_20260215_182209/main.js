const express = require('express');
const app = express();
const port = 3000;

// Simulação de um serviço que gera atividades
function simulateActivity() {
    return new Promise((resolve) => {
        setTimeout(() => {
            resolve({ activity: 'Task completed' });
        }, 2000);
    });
}

app.get('/track-activity', async (req, res) => {
    try {
        const result = await simulateActivity();
        res.json(result);
    } catch (error) {
        console.error('Error tracking activity:', error);
        res.status(500).json({ error: 'Failed to track activity' });
    }
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
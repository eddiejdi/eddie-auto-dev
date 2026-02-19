const axios = require('axios');
const nodemailer = require('nodemailer');

// Configuração do transporter para enviar email
const transporter = nodemailer.createTransport({
  service: 'gmail',
  auth: {
    user: 'seu_email@gmail.com',
    pass: 'sua_senha'
  }
});

// Função para enviar notificações via email
async function enviarNotificacao(subject, body) {
  try {
    const info = await transporter.sendMail({
      from: 'seu_email@gmail.com',
      to: 'destinatario@example.com',
      subject,
      text: body
    });
    console.log('Email enviado:', info.messageId);
  } catch (error) {
    console.error('Erro ao enviar email:', error);
  }
}

// Função para monitorar atividades em JavaScript
async function monitorarAtividades() {
  try {
    const response = await axios.get('https://api.github.com/users/your_username/repositories');
    const repositories = response.data;

    for (const repository of repositories) {
      console.log(`Monitorando repositório: ${repository.name}`);
      // Implemente aqui a lógica para monitorar atividades no repositório
      // Por exemplo, verificar commits recentes ou issues abertas
      // Se houver atividade, enviar notificação via email
      const activity = await axios.get(`https://api.github.com/repos/${repository.name}/commits`);
      if (activity.data.length > 0) {
        const subject = `Novo commit no repositório ${repository.name}`;
        const body = `Um novo commit foi adicionado ao repositório ${repository.name}.`;
        await enviarNotificacao(subject, body);
      }
    }
  } catch (error) {
    console.error('Erro ao monitorar atividades:', error);
  }
}

// Função principal
async function main() {
  try {
    await monitorarAtividades();
    console.log('Monitoramento concluído.');
  } catch (error) {
    console.error('Erro no programa principal:', error);
  }
}

if (require.main === module) {
  main();
}
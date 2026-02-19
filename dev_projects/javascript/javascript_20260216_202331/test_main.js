const { exec } = require('child_process');
const axios = require('axios');

// Classe para representar a atividade no Jira
class Activity {
  constructor(activityId, title) {
    this.activityId = activityId;
    this.title = title;
  }

  // Função para atualizar o status da atividade no Jira
  async updateStatus(status) {
    const url = `https://your-jira-instance.atlassian.net/rest/api/2/issue/${this.activityId}/transitions`;
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': 'Basic your-api-token'
    };

    const payload = {
      "transition": {
        "id": status
      }
    };

    try {
      const response = await axios.post(url, JSON.stringify(payload), { headers });
      console.log(`Status da atividade ${this.title} atualizada para ${response.data.name}`);
    } catch (error) {
      console.error(`Erro ao atualizar status da atividade ${this.title}:`, error);
    }
  }
}

// Função principal do script
async function main() {
  try {
    // Executar o comando "jira-activity" e capturar a saída
    const result = await exec('jira-activity');

    // Verificar se há atividades no resultado
    if (result.stdout) {
      console.log('Atividades encontradas:');
      const activities = JSON.parse(result.stdout);

      // Criar objetos Activity para cada atividade e atualizar o status
      activities.forEach(activity => {
        const activityObj = new Activity(activity.id, activity.title);
        await activityObj.updateStatus(102); // Status de concluído (ID 102)
      });
    } else {
      console.log('Nenhuma atividade encontrada.');
    }
  } catch (error) {
    console.error('Erro ao executar o comando "jira-activity":', error);
  }
}

// Verificar se é um script standalone
if (require.main === module) {
  main();
}
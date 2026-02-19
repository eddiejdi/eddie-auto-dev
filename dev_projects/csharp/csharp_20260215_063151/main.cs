using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

namespace CSharpAgentJiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            // Inicializa a conexão com o Jira
            var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Define as tarefas que você deseja monitorar
            var tasks = new List<Task>
            {
                Task.Run(() => MonitorTask(client, "Task1")),
                Task.Run(() => MonitorTask(client, "Task2"))
            };

            // Aguarda todas as tarefas serem concluídas
            await Task.WhenAll(tasks);
        }

        static async Task MonitorTask(JiraClient client, string taskId)
        {
            try
            {
                var task = await client.GetIssueAsync(taskId);

                Console.WriteLine($"Task {taskId}: {task.Fields.Status.Name}");

                // Simula um tempo de execução para simular o progresso da tarefa
                await Task.Delay(5000);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error monitoring task {taskId}: {ex.Message}");
            }
        }
    }
}
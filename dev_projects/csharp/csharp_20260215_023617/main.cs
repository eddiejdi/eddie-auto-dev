using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Função para criar uma tarefa no Jira
        async Task CreateTaskAsync(string title, string description)
        {
            var task = await client.Tasks.CreateAsync(title, description);
            Console.WriteLine($"Tarefa criada com ID: {task.Id}");
        }

        // Função para monitorar as atividades do usuário
        async Task MonitorUserActivitiesAsync(string username)
        {
            var activities = await client.UserActivities.GetActivitiesAsync(username);
            foreach (var activity in activities)
            {
                Console.WriteLine($"Atividade: {activity.Title} - Status: {activity.Status}");
            }
        }

        // Função principal para executar as tarefas
        async Task MainAsync()
        {
            try
            {
                await CreateTaskAsync("Implement SCRUM-14", "Integrar C# Agent com Jira");
                await MonitorUserActivitiesAsync("your-username");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Erro: {ex.Message}");
            }
        }

        MainAsync();
    }
}
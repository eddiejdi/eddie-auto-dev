using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do cliente Jira
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Função para sincronizar tarefas e projetos
        async Task SyncTasksAndProjects()
        {
            try
            {
                var projects = await jiraClient.GetProjectsAsync();
                foreach (var project in projects)
                {
                    Console.WriteLine($"Project: {project.Name}");

                    var issues = await jiraClient.GetIssuesAsync(project.Key);
                    foreach (var issue in issues)
                    {
                        Console.WriteLine($"  Issue: {issue.Summary}");
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error synchronizing tasks and projects: {ex.Message}");
            }
        }

        // Função para monitorar atividades em tempo real
        async Task MonitorActivity()
        {
            try
            {
                var notifications = await jiraClient.GetNotificationsAsync();
                foreach (var notification in notifications)
                {
                    Console.WriteLine($"Notification: {notification.Subject}");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error monitoring activity: {ex.Message}");
            }
        }

        // Função para automatizar o envio de notificações
        async Task AutomateNotifications()
        {
            try
            {
                var notifications = await jiraClient.GetNotificationsAsync();
                foreach (var notification in notifications)
                {
                    if (notification.Type == "issueCreated")
                    {
                        Console.WriteLine($"Sending notification for issue created: {notification.Subject}");
                        // Implementar a lógica para enviar notificações
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error automating notifications: {ex.Message}");
            }
        }

        // Execução das funções principais
        await SyncTasksAndProjects();
        await MonitorActivity();
        await AutomateNotifications();

        Console.WriteLine("Press any key to exit...");
        Console.ReadKey();
    }
}
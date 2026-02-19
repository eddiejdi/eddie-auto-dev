using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Cria uma instância do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Define a tarefa que você deseja monitorar
        var taskKey = "ABC-123";

        // Monitora a tarefa e imprime o status atual
        while (true)
        {
            try
            {
                var issue = await client.GetIssueAsync(taskKey);
                Console.WriteLine($"Tarefa {taskKey}: Status - {issue.Fields.Status.Name}");
                await Task.Delay(60000); // Aguarda 1 minuto
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Erro ao monitorar tarefa: {ex.Message}");
                break;
            }
        }
    }
}
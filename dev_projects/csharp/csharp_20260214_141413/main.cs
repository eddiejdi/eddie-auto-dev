using System;
using System.Net.Http;
using System.Threading.Tasks;

namespace JiraIntegration
{
    class Program
    {
        static async Task Main(string[] args)
        {
            var client = new HttpClient();
            var url = "https://your-jira-instance.atlassian.net/rest/api/3/issue";

            try
            {
                // Simulando uma requisição para criar um novo issue no Jira
                var response = await client.PostAsync(url, new StringContent("{\"fields\": {\"project\": {\"key\": \"YOUR_PROJECT_KEY\"}, \"summary\": \"Teste C# Agent\", \"description\": \"Criei este issue usando o C# Agent\"}}", System.Text.Encoding.UTF8, "application/json"));

                if (response.IsSuccessStatusCode)
                {
                    Console.WriteLine("Issue criado com sucesso!");
                }
                else
                {
                    Console.WriteLine($"Erro ao criar issue: {response.StatusCode}");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Ocorreu um erro: {ex.Message}");
            }
        }
    }
}
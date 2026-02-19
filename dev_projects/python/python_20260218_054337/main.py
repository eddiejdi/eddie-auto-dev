class Tarefa1:
    def __init__(self):
        self.feature1 = None

    def set_feature1(self, feature1):
        self.feature1 = feature1

    def get_feature1(self):
        return self.feature1

def main():
    tarefa1 = Tarefa1()
    tarefa1.set_feature1("feature1")
    print(tarefa1.get_feature1())

if __name__ == "__main__":
    main()
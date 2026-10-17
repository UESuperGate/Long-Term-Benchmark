export class CreateRoomBasePresenter {
  query: string = '';
  people: string[] = ['Alice', 'Bob', 'Charlie'];
  selectedPerson: string = '';

  updateQuery(value: string): void {
    this.query = value.trim();
  }

  selectPerson(name: string): void {
    this.selectedPerson = name;
  }

  visiblePeople(): string[] {
    if (this.query.length === 0) {
      return this.people.slice();
    }
    const normalized: string = this.query.toLowerCase();
    return this.people.filter((name: string) => name.toLowerCase().includes(normalized));
  }
}

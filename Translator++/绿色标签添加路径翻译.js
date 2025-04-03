if (!this.tags.includes("green")) {
    return;
}
if (!Array.isArray(this.context)) {
    return;
}
const regexs = [
    /^Actors\/\d+\/note$/,
    /^Animations.*?$/,
    /^Armors\/\d+\/note$/,
    /^CommonEvents\/\d+\/name$/,
    /^CommonEvents\/\d+\/list\/\d+\/comment$/,
    /^Enemies\/\d+\/note$/,
    /^Items\/\d+\/note$/,
    /^Map\d{3}\/events\/\d+\/(name|note)$/,
    /^Mapinfos.*?$/,
    /^Skills\/\d+\/note$/,
    /^States\/\d+\/note$/,
    /^System\/switches\/\d+$/,
    /^System\/variables\/\d+$/,
    /^Tilesets.*?$/,
    /^Troops\/\d+\/name$/,
    /^Weapons\/\d+\/note$/,
    /^.*?MZ Plugin Command.*?$/,
    /^.*?Control Variables.*?$/
];
if (!Array.isArray(this.parameters)) {
    this.parameters = []
    for (let i = 0; i < this.context.length; i++) {
        this.parameters.push({
            contextStr: this.context[i]
        });
    }
}
for (let i = 0; i < this.context.length; i++) {
    let context = this.context[i];
    this.parameters[i]["translation"] = "";
    for (const regex of regexs) {
        if (regex.test(context)) {
            this.parameters[i]["translation"] = this.cells[0];
            break;
        }
    }
}
trans.project.files[this.file].parameters[this.rowId] = this.parameters

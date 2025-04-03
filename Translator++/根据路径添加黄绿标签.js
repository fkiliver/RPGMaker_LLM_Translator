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
var count = 0;
for (const context of this.context) {
    for (const regex of regexs) {
        if (regex.test(context)) {
            count++;
            break;
        }
    }
}
var index = this.tags.indexOf("yellow");
if (index > -1) {
    this.tags.splice(index, 1);
}
index = this.tags.indexOf("green");
if (index > -1) {
    this.tags.splice(index, 1);
}
if (count === this.context.length) {
    this.tags.push("yellow");
} else if (count > 0) {
    this.tags.push("green");
}
